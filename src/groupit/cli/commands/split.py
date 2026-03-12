"""
Split command implementation.
"""

import argparse
import os
import subprocess
from typing import TYPE_CHECKING, List

from rich.console import Console

console = Console()

if TYPE_CHECKING:
    from ...core import CommitGroupingAgent


def split_command(args: argparse.Namespace) -> int:
    """
    Execute the split command.

    Current support intentionally stays narrow:
    - the target commit must be the current HEAD or one of its ancestors
    - merge commits are not supported
    - grouped commits must have disjoint file sets
    - commits with file removals are blocked in execute mode
    """
    try:
        from ...core import CommitGroupingAgent
        from ...core.metadata import (
            apply_metadata_overrides,
            extract_commit_metadata,
            metadata_from_repo_defaults,
        )
        from .analyze import (
            _extract_pipeline_overrides,
            _setup_logging_for_command,
            _update_settings_from_args,
            _validate_llm_config,
        )

        _setup_logging_for_command(args)
        _update_settings_from_args(args)

        agent = CommitGroupingAgent()
        target_commit = _resolve_commit(agent, args.commit_hash)
        _ensure_supported_target(agent, target_commit.hexsha)
        _ensure_clean_analysis_target(agent)

        if args.llm != 'none' and not _validate_llm_config(args):
            return 1

        pipeline_overrides = _extract_pipeline_overrides(args)
        result = agent.analyze_commit(
            target_commit.hexsha,
            llm_provider=args.llm if args.llm != 'none' else None,
            llm_api_key=args.api_key,
            output_file=args.output,
            **pipeline_overrides
        )

        if result is None or not result.final_groups:
            console.print("[yellow]No split groups were generated for this commit[/yellow]")
            return 0

        overlapping_files = _find_overlapping_files(result)
        removed_files = _find_removed_files(result)
        rewrite_plan = _build_head_rewrite_plan(agent, target_commit.hexsha, result)
        blockers = _collect_execute_blockers(
            agent,
            target_commit.hexsha,
            result,
            overlapping_files,
            removed_files,
            rewrite_plan,
        )

        if not args.execute:
            console.print("[yellow]Dry run complete. Use --execute to rewrite the commit.[/yellow]")
            _print_execute_notes(blockers)
            return 0

        if blockers:
            console.print("[red]Split execute is blocked:[/red]")
            _print_execute_notes(blockers, style='red')
            return 1

        defaults = _resolve_split_defaults(agent, args)
        preserve_metadata = defaults['preserve_metadata']
        preserve_date_mode = defaults['preserve_date_mode']
        date_increment = defaults['date_increment']
        gpg_sign = defaults['gpg_sign']

        source_metadata = None
        if preserve_metadata or any(
            [
                args.author,
                args.author_email,
                args.author_date,
                args.committer_name,
                args.committer_email,
                args.committer_date,
            ]
        ):
            source_metadata = (
                extract_commit_metadata(agent.repo, target_commit.hexsha)
                if preserve_metadata
                else metadata_from_repo_defaults(agent.repo)
            )
            source_metadata = apply_metadata_overrides(
                source_metadata,
                author_name=args.author,
                author_email=args.author_email,
                author_date=args.author_date,
                committer_name=args.committer_name,
                committer_email=args.committer_email,
                committer_date=args.committer_date,
            )

        if not _confirm_rewrite(agent, result, auto_confirm=args.auto_confirm, commit_hash=target_commit.hexsha):
            return 0

        if _is_head_commit(agent, target_commit.hexsha):
            _rewrite_head_commit(
                agent,
                target_commit.hexsha,
                result,
                rewrite_plan,
                source_metadata=source_metadata,
                date_increment_seconds=date_increment,
                preserve_date_mode=preserve_date_mode,
                gpg_sign=gpg_sign,
            )
        else:
            _rewrite_historical_commit(
                agent,
                target_commit.hexsha,
                result,
                rewrite_plan,
                source_metadata=source_metadata,
                date_increment_seconds=date_increment,
                preserve_date_mode=preserve_date_mode,
                gpg_sign=gpg_sign,
            )

        console.print("[green]Split completed successfully[/green]")
        return 0

    except KeyboardInterrupt:
        console.print("\n[yellow]Split interrupted by user[/yellow]")
        return 130

    except ValueError as e:
        console.print(f"[red]Split failed: {e}[/red]")
        return 1

    except Exception as e:
        console.print(f"[red]Split failed: {e}[/red]")
        if getattr(args, 'debug', False):
            import traceback

            console.print("[red]Traceback:[/red]")
            console.print(traceback.format_exc())
        return 1


def _resolve_commit(agent: 'CommitGroupingAgent', commit_hash: str):
    """Resolve a commit hash and reject root commits for Round 1."""
    try:
        commit = agent.repo.commit(commit_hash)
    except Exception as exc:
        raise ValueError(f"Invalid commit hash: {commit_hash}") from exc

    if not commit.parents:
        raise ValueError("Split does not support root commits in Round 1")

    if len(commit.parents) > 1:
        raise ValueError("Split does not support merge commits in Round 1")

    return commit


def _find_overlapping_files(result) -> List[str]:
    """Return files that appear in more than one final group."""
    seen = set()
    overlapping = set()

    for group in result.final_groups:
        for file_path in group.files:
            if file_path in seen:
                overlapping.add(file_path)
            else:
                seen.add(file_path)

    return sorted(overlapping)


def _find_removed_files(result) -> List[str]:
    """Return files that include removal blocks in the grouped result."""
    removed = set()

    for group in result.final_groups:
        for block in getattr(group, 'blocks', []):
            if getattr(block, 'kind', None) == 'removal':
                removed.add(block.file_path)

    return sorted(removed)


def _is_head_commit(agent: 'CommitGroupingAgent', commit_hash: str) -> bool:
    """Return True when the target commit is the current HEAD commit."""
    return agent.repo.head.commit.hexsha == agent.repo.commit(commit_hash).hexsha


def _has_tracked_worktree_changes(agent: 'CommitGroupingAgent') -> bool:
    """Return True when tracked files are staged or modified."""
    return agent.repo.is_dirty(untracked_files=False)


def _ensure_round1_target(agent: 'CommitGroupingAgent', commit_hash: str) -> None:
    """Reject targets outside the supported Round 1 scope."""
    if not _is_head_commit(agent, commit_hash):
        raise ValueError("Round 1 split currently supports only the current HEAD commit")


def _ensure_clean_analysis_target(agent: 'CommitGroupingAgent') -> None:
    """Reject dirty tracked state because commit analysis reads the working tree."""
    if _has_tracked_worktree_changes(agent):
        raise ValueError(
            "Split requires a clean tracked worktree because analysis reads current file contents"
        )


def _is_ancestor_of_head(agent: 'CommitGroupingAgent', commit_hash: str) -> bool:
    """Return True when the target commit is reachable from HEAD."""
    try:
        agent.repo.git.merge_base('--is-ancestor', commit_hash, 'HEAD')
        return True
    except Exception:
        return False


def _ensure_supported_target(agent: 'CommitGroupingAgent', commit_hash: str) -> None:
    """Reject targets outside the supported split scope."""
    if not _is_ancestor_of_head(agent, commit_hash):
        raise ValueError("Split can only rewrite commits that are reachable from the current HEAD")


def _git_config_bool(agent: 'CommitGroupingAgent', key: str, default: bool) -> bool:
    """Read a boolean git config value."""
    try:
        value = agent.repo.config_reader().get_value('groupit', key)
    except Exception:
        return default
    return str(value).lower() in ('true', '1', 'yes', 'on')


def _git_config_string(agent: 'CommitGroupingAgent', key: str, default: str | None = None) -> str | None:
    """Read a string git config value."""
    try:
        return agent.repo.config_reader().get_value('groupit', key)
    except Exception:
        return default


def _git_config_int(agent: 'CommitGroupingAgent', key: str, default: int) -> int:
    """Read an integer git config value."""
    try:
        return int(agent.repo.config_reader().get_value('groupit', key))
    except Exception:
        return default


def _resolve_split_defaults(agent: 'CommitGroupingAgent', args) -> dict:
    """Resolve split defaults from CLI, environment, and git config."""
    preserve_metadata = (
        args.preserve_metadata
        or os.getenv('GROUPIT_GIT_PRESERVE_METADATA', '').lower() in ('true', '1', 'yes')
        or _git_config_bool(agent, 'preserve', False)
    )
    preserve_date_mode = (
        args.preserve_date
        or os.getenv('GROUPIT_GIT_PRESERVE_DATE')
        or _git_config_string(agent, 'preserveDate', 'all')
        or 'all'
    )
    date_increment = (
        args.date_increment
        if args.date_increment is not None
        else int(os.getenv('GROUPIT_GIT_DATE_INCREMENT', _git_config_int(agent, 'dateIncrement', 1)))
    )
    gpg_sign = (
        args.gpg_sign
        or os.getenv('GROUPIT_GIT_GPG_SIGN_KEY')
        or _git_config_string(agent, 'gpgKey')
    )
    return {
        'preserve_metadata': preserve_metadata,
        'preserve_date_mode': preserve_date_mode,
        'date_increment': date_increment,
        'gpg_sign': gpg_sign,
    }


def _collect_execute_blockers(
    agent: 'CommitGroupingAgent',
    commit_hash: str,
    result,
    overlapping_files: List[str],
    removed_files: List[str],
    rewrite_plan,
) -> List[str]:
    """Return the reasons execute mode should refuse to rewrite history."""
    blockers = []
    changed_files = _changed_files_for_commit(agent, commit_hash)
    grouped_files = _grouped_files(result)

    if _has_tracked_worktree_changes(agent):
        blockers.append("Repository has staged or modified tracked changes.")

    if changed_files != grouped_files:
        details = []
        missing_files = sorted(changed_files - grouped_files)
        extra_files = sorted(grouped_files - changed_files)
        if missing_files:
            details.append("missing " + ", ".join(missing_files))
        if extra_files:
            details.append("unexpected " + ", ".join(extra_files))
        blockers.append(
            "Grouped files do not exactly cover the target commit changes"
            + (f": {'; '.join(details)}" if details else ".")
        )

    for group_id, patch_text in rewrite_plan.items():
        if not patch_text:
            blockers.append(
                f"Could not build a patch plan for group {group_id}; block-level rewrite is not safe."
            )

    return blockers


def _print_execute_notes(notes: List[str], style: str = 'yellow') -> None:
    """Print a flat list of execution notes."""
    for note in notes:
        console.print(f"[{style}]- {note}[/{style}]")


def _confirm_rewrite(agent: 'CommitGroupingAgent', result, auto_confirm: bool, commit_hash: str) -> bool:
    """Confirm the rewrite before any history mutation occurs."""
    if auto_confirm:
        return True

    agent._show_commit_summary(result.final_groups)

    from rich.prompt import Confirm

    return Confirm.ask(f"Proceed with rewriting commit {commit_hash[:8]}?")


def _grouped_files(result) -> set[str]:
    """Return the full set of files referenced by final groups."""
    files = set()
    for group in result.final_groups:
        files.update(group.files)
    return files


def _changed_files_for_commit(agent: 'CommitGroupingAgent', commit_hash: str) -> set[str]:
    """Return the file set changed by the target commit."""
    output = agent.repo.git.diff('--name-only', f'{commit_hash}^', commit_hash)
    return {line for line in output.splitlines() if line}


def _restore_original_head(agent: 'CommitGroupingAgent', original_head: str) -> None:
    """Restore the repository to its original HEAD after a failed rewrite."""
    subprocess.run(
        ['git', 'reset', '--hard', original_head],
        check=True,
        cwd=agent.repo_root,
    )


def _descendant_commits_after_target(agent: 'CommitGroupingAgent', commit_hash: str) -> List[str]:
    """Return descendant commits after the target, ordered oldest to newest."""
    output = agent.repo.git.rev_list('--reverse', f'{commit_hash}..HEAD')
    return [line for line in output.splitlines() if line]


def _run_git(agent: 'CommitGroupingAgent', *args: str) -> None:
    """Run a git command in the repository root."""
    subprocess.run(
        ['git', *args],
        check=True,
        cwd=agent.repo_root,
    )


def _matches_hunk(group, file_path: str, hunk) -> bool:
    """Return True when a group owns a specific hunk in a file."""
    for block in getattr(group, 'blocks', []):
        if block.file_path != file_path:
            continue

        if getattr(block, 'kind', None) == 'removal':
            return True

        line_start = hunk.target_start if hunk.target_length else hunk.source_start
        line_end = line_start + max(hunk.target_length, hunk.source_length, 1) - 1

        if block.start_line <= line_end and block.end_line >= line_start:
            return True

    return False


def _render_file_patch(file_patch, hunks: List) -> str:
    """Render a patch text for a file and a subset of its hunks."""
    if not hunks:
        return ''

    rendered = (
        str(file_patch.patch_info)
        + f"--- {file_patch.source_file}\n"
        + f"+++ {file_patch.target_file}\n"
        + ''.join(str(hunk) for hunk in hunks)
    )
    if not rendered.endswith('\n'):
        rendered += '\n'
    return rendered


def _build_head_rewrite_plan(agent: 'CommitGroupingAgent', commit_hash: str, result) -> dict:
    """Build per-group patch texts for HEAD block-level rewrite."""
    from ...core.git_operations import collect_commit_diff

    patch = collect_commit_diff(agent.repo, commit_hash)
    group_hunks = {group.group_id: [] for group in result.final_groups}

    for file_patch in patch:
        file_groups = [
            group
            for group in result.final_groups
            if any(block.file_path == file_patch.path for block in getattr(group, 'blocks', []))
        ]

        for hunk in file_patch:
            owners = [
                group.group_id
                for group in result.final_groups
                if _matches_hunk(group, file_patch.path, hunk)
            ]

            if len(owners) != 1:
                owners = []

            if not owners and len(file_groups) == len(file_patch):
                sorted_groups = sorted(
                    file_groups,
                    key=lambda group: min(
                        block.start_line for block in group.blocks if block.file_path == file_patch.path
                    ),
                )
                hunk_index = list(file_patch).index(hunk)
                owners = [sorted_groups[hunk_index].group_id]

            if len(owners) != 1:
                return {group.group_id: '' for group in result.final_groups}

            group_hunks[owners[0]].append((file_patch, hunk))

    group_patches = {}
    for group in result.final_groups:
        per_file = {}
        for file_patch, hunk in group_hunks[group.group_id]:
            per_file.setdefault(file_patch.path, {'file_patch': file_patch, 'hunks': []})
            per_file[file_patch.path]['hunks'].append(hunk)

        patch_text = ''.join(
            _render_file_patch(data['file_patch'], data['hunks'])
            for data in per_file.values()
        )
        group_patches[group.group_id] = patch_text

    return group_patches


def _apply_group_patch(agent: 'CommitGroupingAgent', patch_text: str) -> None:
    """Apply a prepared group patch to index and working tree."""
    subprocess.run(
        ['git', 'apply', '--index', '--unidiff-zero', '-'],
        input=patch_text.encode('utf-8'),
        check=True,
        cwd=agent.repo_root,
    )


def _rewrite_commit_from_parent(
    agent: 'CommitGroupingAgent',
    commit_hash: str,
    result,
    rewrite_plan,
    source_metadata=None,
    date_increment_seconds: int = 1,
    preserve_date_mode: str = 'all',
    gpg_sign=None,
) -> None:
    """Rewrite the target commit from its parent using block-level patches."""
    original_head = agent.repo.head.commit.hexsha
    parent_hash = agent.repo.commit(commit_hash).parents[0].hexsha
    expected_commits = len(result.final_groups)

    try:
        _run_git(agent, 'reset', '--hard', parent_hash)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("Failed to reset HEAD to the target commit parent") from exc

    try:
        created_count = 0
        for index, group in enumerate(result.final_groups):
            patch_text = rewrite_plan[group.group_id]
            _apply_group_patch(agent, patch_text)
            agent.commit_staged_changes(
                message=group.commit_message or f"chore: Update {len(group.files)} files",
                commit_metadata=source_metadata,
                commit_index=index,
                date_increment_seconds=date_increment_seconds,
                preserve_date_mode=preserve_date_mode,
                gpg_sign=gpg_sign,
            )
            created_count += 1

        if created_count != expected_commits:
            raise RuntimeError(
                f"Created {created_count} of {expected_commits} expected commits; repository may require manual recovery."
            )

        if _has_tracked_worktree_changes(agent):
            raise RuntimeError("Split left tracked changes in the repository after rewriting commit patches.")

    except Exception:
        _restore_original_head(agent, original_head)
        raise

    created_commits = sum(1 for _ in agent.repo.iter_commits(f'{parent_hash}..HEAD'))
    if created_commits != expected_commits:
        _restore_original_head(agent, original_head)
        raise RuntimeError(
            f"Created {created_commits} of {expected_commits} expected commits; repository may require manual recovery."
        )


def _rewrite_head_commit(
    agent: 'CommitGroupingAgent',
    commit_hash: str,
    result,
    rewrite_plan,
    source_metadata=None,
    date_increment_seconds: int = 1,
    preserve_date_mode: str = 'all',
    gpg_sign=None,
) -> None:
    """Rewrite the current HEAD commit into grouped commits."""
    parent_hash = agent.repo.commit(commit_hash).parents[0].hexsha
    console.print(f"[cyan]Rewriting HEAD commit {commit_hash[:8]} from parent {parent_hash[:8]}[/cyan]")
    _rewrite_commit_from_parent(
        agent,
        commit_hash,
        result,
        rewrite_plan,
        source_metadata=source_metadata,
        date_increment_seconds=date_increment_seconds,
        preserve_date_mode=preserve_date_mode,
        gpg_sign=gpg_sign,
    )


def _rewrite_historical_commit(
    agent: 'CommitGroupingAgent',
    commit_hash: str,
    result,
    rewrite_plan,
    source_metadata=None,
    date_increment_seconds: int = 1,
    preserve_date_mode: str = 'all',
    gpg_sign=None,
) -> None:
    """Rewrite a non-HEAD ancestor commit and replay descendants."""
    original_head = agent.repo.head.commit.hexsha
    parent_hash = agent.repo.commit(commit_hash).parents[0].hexsha
    descendant_commits = _descendant_commits_after_target(agent, commit_hash)

    console.print(
        f"[cyan]Rewriting historical commit {commit_hash[:8]} from parent {parent_hash[:8]} "
        f"and replaying {len(descendant_commits)} descendant commits[/cyan]"
    )

    _rewrite_commit_from_parent(
        agent,
        commit_hash,
        result,
        rewrite_plan,
        source_metadata=source_metadata,
        date_increment_seconds=date_increment_seconds,
        preserve_date_mode=preserve_date_mode,
        gpg_sign=gpg_sign,
    )

    try:
        for descendant in descendant_commits:
            _run_git(agent, 'cherry-pick', descendant)
    except Exception:
        try:
            _run_git(agent, 'cherry-pick', '--abort')
        except Exception:
            pass
        _restore_original_head(agent, original_head)
        raise
