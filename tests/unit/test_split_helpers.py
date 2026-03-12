from pathlib import Path
from types import SimpleNamespace

from git import Repo

from groupit.cli.commands.split import (
    _collect_execute_blockers,
    _descendant_commits_after_target,
    _ensure_clean_analysis_target,
    _ensure_supported_target,
    _find_removed_files,
    _find_overlapping_files,
    _is_ancestor_of_head,
    _is_head_commit,
    _resolve_split_defaults,
    _resolve_commit,
)


def test_find_overlapping_files_returns_duplicates_once():
    result = SimpleNamespace(
        final_groups=[
            SimpleNamespace(files=['a.py', 'b.py']),
            SimpleNamespace(files=['b.py', 'c.py']),
            SimpleNamespace(files=['d.py']),
        ]
    )

    assert _find_overlapping_files(result) == ['b.py']


def test_resolve_commit_rejects_root_commit(tmp_path):
    repo = _init_repo_with_two_commits(tmp_path)
    root_commit = repo.commit('HEAD~1')
    agent = SimpleNamespace(repo=repo)

    try:
        _resolve_commit(agent, root_commit.hexsha)
    except ValueError as exc:
        assert 'root commits' in str(exc)
    else:
        raise AssertionError('expected ValueError for root commit')


def test_collect_execute_blockers_reports_missing_patch_plan(tmp_path):
    repo = _init_repo_with_three_commits(tmp_path)
    agent = SimpleNamespace(repo=repo)
    non_head_commit = repo.commit('HEAD~1').hexsha
    result = SimpleNamespace(
        final_groups=[
            SimpleNamespace(files=['app.py'], blocks=[]),
        ]
    )

    blockers = _collect_execute_blockers(agent, non_head_commit, result, ['app.py'], [], {1: ''})

    assert any('patch plan' in blocker for blocker in blockers)


def test_is_head_commit_true_for_head(tmp_path):
    repo = _init_repo_with_two_commits(tmp_path)
    agent = SimpleNamespace(repo=repo)

    assert _is_head_commit(agent, repo.head.commit.hexsha) is True


def test_find_removed_files_returns_removal_paths():
    result = SimpleNamespace(
        final_groups=[
            SimpleNamespace(
                files=['gone.py'],
                blocks=[SimpleNamespace(file_path='gone.py', kind='removal')],
            ),
            SimpleNamespace(
                files=['keep.py'],
                blocks=[SimpleNamespace(file_path='keep.py', kind='function_definition')],
            ),
        ]
    )

    assert _find_removed_files(result) == ['gone.py']


def test_resolve_commit_rejects_merge_commit(tmp_path):
    repo = _init_repo_with_merge_commit(tmp_path)
    agent = SimpleNamespace(repo=repo)

    try:
        _resolve_commit(agent, repo.head.commit.hexsha)
    except ValueError as exc:
        assert 'merge commits' in str(exc)
    else:
        raise AssertionError('expected ValueError for merge commit')


def test_ensure_clean_analysis_target_rejects_dirty_tracked_changes(tmp_path):
    repo = _init_repo_with_two_commits(tmp_path)
    agent = SimpleNamespace(repo=repo)
    tracked_file = Path(repo.working_tree_dir) / 'app.py'
    tracked_file.write_text("print('dirty')\n", encoding='utf-8')

    try:
        _ensure_clean_analysis_target(agent)
    except ValueError as exc:
        assert 'clean tracked worktree' in str(exc)
    else:
        raise AssertionError('expected ValueError for dirty tracked files')


def test_collect_execute_blockers_reports_file_coverage_mismatch(tmp_path):
    repo = _init_repo_with_two_commits(tmp_path)
    agent = SimpleNamespace(repo=repo)
    result = SimpleNamespace(
        final_groups=[
            SimpleNamespace(files=['different.py'], blocks=[]),
        ]
    )

    blockers = _collect_execute_blockers(agent, repo.head.commit.hexsha, result, [], [], {1: 'patch'})

    assert any('exactly cover' in blocker for blocker in blockers)


def test_ensure_supported_target_allows_head_ancestor(tmp_path):
    repo = _init_repo_with_three_commits(tmp_path)
    agent = SimpleNamespace(repo=repo)

    _ensure_supported_target(agent, repo.commit('HEAD~1').hexsha)
    assert _is_ancestor_of_head(agent, repo.commit('HEAD~1').hexsha) is True


def test_ensure_supported_target_rejects_non_ancestor_commit(tmp_path):
    repo = _init_repo_with_side_branch_commit(tmp_path)
    agent = SimpleNamespace(repo=repo)
    side_branch_commit = repo.commit('side').hexsha

    try:
        _ensure_supported_target(agent, side_branch_commit)
    except ValueError as exc:
        assert 'reachable from the current HEAD' in str(exc)
    else:
        raise AssertionError('expected ValueError for non-ancestor commit')


def test_descendant_commits_after_target_returns_oldest_first(tmp_path):
    repo = _init_repo_with_three_commits(tmp_path)
    agent = SimpleNamespace(repo=repo)

    descendants = _descendant_commits_after_target(agent, repo.commit('HEAD~1').hexsha)

    assert descendants == [repo.head.commit.hexsha]


def test_resolve_split_defaults_reads_git_config(tmp_path):
    repo = _init_repo_with_two_commits(tmp_path)
    with repo.config_writer() as config:
        config.set_value('groupit', 'preserve', 'true')
        config.set_value('groupit', 'preserveDate', 'single')
        config.set_value('groupit', 'dateIncrement', '9')
        config.set_value('groupit', 'gpgKey', 'ABC123')

    agent = SimpleNamespace(repo=repo)
    args = SimpleNamespace(
        preserve_metadata=False,
        preserve_date=None,
        date_increment=None,
        gpg_sign=None,
    )

    defaults = _resolve_split_defaults(agent, args)

    assert defaults['preserve_metadata'] is True
    assert defaults['preserve_date_mode'] == 'single'
    assert defaults['date_increment'] == 9
    assert defaults['gpg_sign'] == 'ABC123'


def _init_repo_with_two_commits(tmp_path: Path) -> Repo:
    repo_path = tmp_path / 'repo'
    repo_path.mkdir()

    repo = Repo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value('user', 'name', 'Test User')
        config.set_value('user', 'email', 'test@example.com')

    tracked_file = repo_path / 'app.py'
    tracked_file.write_text("print('one')\n", encoding='utf-8')
    repo.index.add(['app.py'])
    repo.index.commit('feat: initial commit')

    tracked_file.write_text("print('two')\n", encoding='utf-8')
    repo.index.add(['app.py'])
    repo.index.commit('feat: update app')

    return repo


def _init_repo_with_three_commits(tmp_path: Path) -> Repo:
    repo = _init_repo_with_two_commits(tmp_path)
    tracked_file = Path(repo.working_tree_dir) / 'app.py'
    tracked_file.write_text("print('three')\n", encoding='utf-8')
    repo.index.add(['app.py'])
    repo.index.commit('feat: third change')
    return repo


def _init_repo_with_merge_commit(tmp_path: Path) -> Repo:
    repo = _init_repo_with_two_commits(tmp_path)
    default_branch = repo.active_branch.name
    repo.git.checkout('-b', 'feature', 'HEAD~1')

    feature_file = Path(repo.working_tree_dir) / 'feature.py'
    feature_file.write_text("print('feature')\n", encoding='utf-8')
    repo.index.add(['feature.py'])
    repo.index.commit('feat: feature branch change')

    repo.git.checkout(default_branch)
    app_file = Path(repo.working_tree_dir) / 'app.py'
    app_file.write_text("print('mainline')\n", encoding='utf-8')
    repo.index.add(['app.py'])
    repo.index.commit('feat: main branch change')
    repo.git.merge('feature', '--no-ff', '-m', 'merge feature')

    return repo


def _init_repo_with_side_branch_commit(tmp_path: Path) -> Repo:
    repo = _init_repo_with_three_commits(tmp_path)
    default_branch = repo.active_branch.name
    repo.git.checkout('-b', 'side', 'HEAD~2')

    side_file = Path(repo.working_tree_dir) / 'side.py'
    side_file.write_text("print('side')\n", encoding='utf-8')
    repo.index.add(['side.py'])
    repo.index.commit('feat: side branch change')
    repo.git.checkout(default_branch)

    return repo
