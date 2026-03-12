"""
Main agent for commit grouping that integrates with Git repositories.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional

from git import Repo
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .models import CommitGroup, GroupingResult
from .pipeline import CommitGroupingPipeline
from .git_operations import collect_diff, collect_commit_diff, build_blocks, materialize_commit_tree
from .metadata import (
    CommitMetadata,
    build_git_env_for_metadata,
    build_preserved_commit_kwargs,
    offset_datetime,
)
from ..config import get_settings, get_logger

logger = get_logger(__name__)
console = Console()


class CommitGroupingAgent:
    """
    Main agent for orchestrating commit grouping operations.
    
    This agent handles:
    - Git repository interactions
    - Pipeline orchestration
    - Result presentation and persistence
    - Commit creation
    """
    
    def __init__(self, repo_path: Optional[Path] = None):
        self.repo_path = repo_path or Path.cwd()
        self.settings = get_settings()
        
        # Initialize Git repository
        try:
            self.repo = Repo(self.repo_path)
            self.repo_root = Path(self.repo.working_tree_dir)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Git repository at {self.repo_path}: {e}")
        
        # Initialize pipeline
        self.pipeline = CommitGroupingPipeline(self.repo_root, self.settings)
        
        logger.info(f"Initialized CommitGroupingAgent for repository: {self.repo_root}")
    
    def analyze_changes(
        self,
        staged: bool = False,
        llm_provider: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        output_file: Optional[str] = None,
        **pipeline_overrides
    ) -> Optional[GroupingResult]:
        """
        Analyze Git changes and create commit groups
        
        Args:
            staged: Analyze only staged changes
            llm_provider: LLM provider to use
            llm_api_key: API key for LLM provider
            output_file: File to save results to
            **pipeline_overrides: Override pipeline settings
        
        Returns:
            GroupingResult or None if no changes found
        """
        mode_label = 'Staged changes' if staged else 'Working directory changes'
        patch = collect_diff(self.repo, staged=staged)
        return self.analyze_patch(
            patch=patch,
            llm_provider=llm_provider,
            llm_api_key=llm_api_key,
            output_file=output_file,
            mode_label=mode_label,
            **pipeline_overrides
        )

    def analyze_commit(
        self,
        commit_hash: str,
        llm_provider: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        output_file: Optional[str] = None,
        **pipeline_overrides
    ) -> Optional[GroupingResult]:
        """Analyze the diff introduced by a specific commit."""
        patch = collect_commit_diff(self.repo, commit_hash)
        with tempfile.TemporaryDirectory(prefix='groupit-commit-snapshot-') as temp_dir:
            snapshot_root = Path(temp_dir)
            materialize_commit_tree(self.repo, commit_hash, snapshot_root)
            return self.analyze_patch(
                patch=patch,
                llm_provider=llm_provider,
                llm_api_key=llm_api_key,
                output_file=output_file,
                mode_label=f'Commit {commit_hash[:8]}',
                source_root=snapshot_root,
                **pipeline_overrides
            )

    def analyze_patch(
        self,
        patch,
        llm_provider: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        output_file: Optional[str] = None,
        mode_label: str = 'Patch changes',
        source_root: Optional[Path] = None,
        **pipeline_overrides
    ) -> Optional[GroupingResult]:
        """Analyze a prepared patch and create commit groups."""
        console.print(Panel.fit(
            f"[bold]Commit Grouping Analysis[/bold]\n"
            f"Repository: {self.repo_path}\n"
            f"Mode: {mode_label}\n"
            f"LLM Provider: {llm_provider or self.settings.llm.provider}",
            border_style="blue"
        ))

        try:
            if not str(patch).strip():
                console.print("[yellow]No changes detected[/yellow]")
                return None

            blocks = build_blocks(source_root or self.repo_root, patch)
            if not blocks:
                console.print("[yellow]No analyzable blocks found[/yellow]")
                return None

            console.print(f"[green]Found {len(blocks)} change blocks in {len(set(b.file_path for b in blocks))} files[/green]")

            result = self.pipeline.execute(
                change_blocks=blocks,
                llm_provider=llm_provider,
                llm_api_key=llm_api_key,
                **pipeline_overrides
            )

            if output_file:
                self.save_results(result, output_file)

            self.display_results(result)
            return result

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            console.print(f"[red]Analysis failed: {e}[/red]")
            raise
    
    def create_commits(
        self,
        result: GroupingResult,
        dry_run: bool = True,
        auto_confirm: bool = False,
        commit_metadata: Optional[CommitMetadata] = None,
        date_increment_seconds: int = 1,
        preserve_date_mode: str = 'all',
        gpg_sign: Optional[str] = None,
    ) -> int:
        """
        Create actual Git commits from grouping result
        
        Args:
            result: GroupingResult from analysis
            dry_run: If True, don't actually create commits
            auto_confirm: If True, don't ask for confirmation
            commit_metadata: Source metadata to preserve across replacement commits
            date_increment_seconds: Seconds added between preserved commit dates
            preserve_date_mode: 'all' to preserve each rewritten date, 'single' for first only
            gpg_sign: Optional GPG key id for signed commits
        """
        if not result or not result.final_groups:
            console.print("[yellow]No groups to commit[/yellow]")
            return 0
        
        console.rule("[bold]Creating Commits[/bold]")
        
        if not auto_confirm and not dry_run:
            # Show summary and ask for confirmation
            self._show_commit_summary(result.final_groups)
            
            from rich.prompt import Confirm
            if not Confirm.ask("Proceed with creating commits?"):
                console.print("[yellow]Commit creation cancelled[/yellow]")
                return 0
        
        # Create commits
        successful_commits = 0
        for i, group in enumerate(result.final_groups, 1):
            console.print(f"\n[cyan]Creating commit {i}/{len(result.final_groups)}[/cyan]")
            
            # Ensure we have a commit message
            if not group.commit_message:
                group.commit_message = f"chore: Update {len(group.files)} files"
            
            console.print(f"Message: {group.commit_message}")
            console.print(f"Files: {', '.join(group.files[:3])}")
            if len(group.files) > 3:
                console.print(f"  ... and {len(group.files) - 3} more files")
            
            if not dry_run:
                try:
                    # Reset index to clean state
                    self.repo.index.reset()
                    
                    # Add only the files for this group
                    self.repo.index.add(group.files)

                    commit = self.commit_staged_changes(
                        message=group.commit_message,
                        commit_metadata=commit_metadata,
                        commit_index=i - 1,
                        date_increment_seconds=date_increment_seconds,
                        preserve_date_mode=preserve_date_mode,
                        gpg_sign=gpg_sign,
                    )
                    console.print(f"[green]✓ Committed: {commit.hexsha[:8]}[/green]")
                    successful_commits += 1
                    
                except Exception as e:
                    console.print(f"[red]✗ Failed to commit: {e}[/red]")
                    logger.error(f"Failed to create commit for group {group.group_id}: {e}")
                    raise RuntimeError(
                        f"Failed to create commit for group {group.group_id}"
                    ) from e
            else:
                if commit_metadata:
                    seconds_offset = (i - 1) * date_increment_seconds
                    console.print(
                        f"[dim]Preserving author {commit_metadata.author_name} "
                        f"<{commit_metadata.author_email}>[/dim]"
                    )
                    console.print(
                        f"[dim]Preserving committer {commit_metadata.committer_name} "
                        f"<{commit_metadata.committer_email}>[/dim]"
                    )
                    console.print(
                        f"[dim]Author date: {offset_datetime(commit_metadata.authored_date, seconds_offset).isoformat()}[/dim]"
                    )
                if gpg_sign:
                    console.print(f"[dim]GPG sign: {gpg_sign}[/dim]")
                console.print("[yellow]→ Dry run (not committed)[/yellow]")
        
        if dry_run:
            console.print("\n[yellow]This was a dry run. Use --execute to actually create commits.[/yellow]")
        else:
            console.print(f"\n[green]Successfully created {len(result.final_groups)} commits[/green]")

        return len(result.final_groups) if dry_run else successful_commits

    def commit_staged_changes(
        self,
        message: str,
        commit_metadata: Optional[CommitMetadata] = None,
        commit_index: int = 0,
        date_increment_seconds: int = 1,
        preserve_date_mode: str = 'all',
        gpg_sign: Optional[str] = None,
    ):
        """Commit the current staged index state with optional preserved metadata."""
        commit_kwargs = {'message': message}

        if gpg_sign:
            env = os.environ.copy()
            if commit_metadata:
                env.update(
                    build_git_env_for_metadata(
                        commit_metadata,
                        commit_index,
                        date_increment_seconds,
                        preserve_date_mode,
                    )
                )
            subprocess.run(
                ['git', 'commit', '-m', message, f'--gpg-sign={gpg_sign}'],
                check=True,
                cwd=self.repo_root,
                env=env,
            )
            return self.repo.head.commit

        if commit_metadata:
            commit_kwargs.update(
                build_preserved_commit_kwargs(
                    commit_metadata,
                    commit_index,
                    date_increment_seconds,
                    preserve_date_mode,
                )
            )

        return self.repo.index.commit(**commit_kwargs)
    
    def load_results(self, input_file: str) -> GroupingResult:
        """
        Load GroupingResult from JSON file
        
        Args:
            input_file: Path to JSON file
        
        Returns:
            GroupingResult object
        """
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            result = GroupingResult.from_dict(data)
            logger.info(f"Loaded results from {input_file}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to load results from {input_file}: {e}")
            raise RuntimeError(f"Failed to load results: {e}")
    
    def save_results(self, result: GroupingResult, output_file: str) -> None:
        """
        Save GroupingResult to JSON file
        
        Args:
            result: GroupingResult to save
            output_file: Path to output file
        """
        try:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
            
            console.print(f"[green]Results saved to {output_file}[/green]")
            logger.info(f"Saved results to {output_file}")
            
        except Exception as e:
            logger.error(f"Failed to save results to {output_file}: {e}")
            console.print(f"[red]Failed to save results: {e}[/red]")
    
    def display_results(self, result: GroupingResult) -> None:
        """Display results in a formatted way"""
        console.rule("[bold]Analysis Results[/bold]")
        
        # Summary table
        summary_table = Table(show_header=True, header_style="bold magenta")
        summary_table.add_column("Stage", style="cyan")
        summary_table.add_column("Groups", style="white")
        summary_table.add_column("Description", style="dim")
        
        stage_summary = result.get_stage_summary()
        summary_table.add_row("Primary", str(stage_summary['stage1_primary']), "Structural clustering")
        summary_table.add_row("Summary", str(stage_summary['stage2_summary']), "Natural language summaries")
        summary_table.add_row("Semantic", str(stage_summary['stage3_semantic']), "LLM-based grouping")
        summary_table.add_row("Final", str(stage_summary['stage4_final']), "With commit messages")
        
        console.print(Panel(summary_table, title="Pipeline Summary", border_style="blue"))
        
        # Final groups
        console.rule("[bold]Final Commit Groups[/bold]")
        
        for group in result.final_groups:
            group_table = Table(show_header=True, header_style="bold cyan")
            group_table.add_column("Property", style="cyan", width=20)
            group_table.add_column("Value", style="white")
            
            group_table.add_row("Group ID", str(group.group_id))
            group_table.add_row("Files", str(len(group.files)))
            group_table.add_row("Changes", str(len(group.blocks)))
            
            if group.semantic_theme:
                group_table.add_row("Theme", group.semantic_theme)
            
            if group.summary:
                summary_text = group.summary[:100] + "..." if len(group.summary) > 100 else group.summary
                group_table.add_row("Summary", summary_text)
            
            if group.commit_message:
                message_text = group.commit_message[:150] + "..." if len(group.commit_message) > 150 else group.commit_message
                group_table.add_row("Commit Message", message_text)
            
            # File list
            file_list = "\n".join(group.files[:5])
            if len(group.files) > 5:
                file_list += f"\n... and {len(group.files)-5} more"
            group_table.add_row("Files", file_list)
            
            panel = Panel(
                group_table,
                title=f"Group {group.group_id}",
                border_style="green"
            )
            console.print(panel)
        
        # Execution summary
        console.print(f"\n[blue]Execution time: {result.execution_time:.2f} seconds[/blue]")
        console.print(f"[blue]Compression ratio: {result.compression_ratio:.2f} (final/initial groups)[/blue]")
    
    def _show_commit_summary(self, groups: List[CommitGroup]) -> None:
        """Show a summary of commits to be created"""
        console.rule("[bold]Commit Summary[/bold]")
        
        summary_table = Table(show_header=True, header_style="bold cyan")
        summary_table.add_column("Group", style="cyan", width=8)
        summary_table.add_column("Files", style="white", width=8)
        summary_table.add_column("Message", style="green")
        
        for group in groups:
            message = group.commit_message or "No message"
            if len(message) > 60:
                message = message[:60] + "..."
            
            summary_table.add_row(
                str(group.group_id),
                str(len(group.files)),
                message
            )
        
        console.print(summary_table)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current repository and agent status"""
        try:
            repo_status = {
                'repository_path': str(self.repo_root),
                'current_branch': self.repo.active_branch.name,
                'is_dirty': self.repo.is_dirty(),
                'untracked_files': len(self.repo.untracked_files),
                'staged_files': len([item for item in self.repo.index.diff("HEAD")]),
                'modified_files': len([item for item in self.repo.index.diff(None)])
            }
        except Exception as e:
            repo_status = {'error': str(e)}
        
        pipeline_stats = self.pipeline.get_pipeline_statistics()
        
        return {
            'agent_version': '3.0',
            'repository': repo_status,
            'pipeline': pipeline_stats,
            'settings': {
                'llm_provider': self.settings.llm.provider,
                'debug_mode': self.settings.debug,
                'performance_caching': self.settings.performance.enable_caching
            }
        }
