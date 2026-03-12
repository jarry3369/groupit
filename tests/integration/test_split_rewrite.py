from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import importlib
import sys
import types

from git import Actor, Repo

from groupit.cli.commands.split import _build_head_rewrite_plan, _rewrite_head_commit, _rewrite_historical_commit
from groupit.core.metadata import extract_commit_metadata, offset_datetime


def test_rewrite_historical_commit_replays_descendants(tmp_path):
    repo = _init_repo_with_target_and_descendant(tmp_path)
    target_commit = repo.commit('HEAD~1')
    result = SimpleNamespace(
        final_groups=[
            SimpleNamespace(
                group_id=1,
                files=['app.py'],
                commit_message='split: target rewrite',
                blocks=[SimpleNamespace(file_path='app.py', start_line=1, end_line=1, kind='hunk')],
            )
        ]
    )
    agent = _make_lightweight_agent(repo)
    rewrite_plan = _build_head_rewrite_plan(agent, target_commit.hexsha, result)

    _rewrite_historical_commit(
        agent,
        target_commit.hexsha,
        result,
        rewrite_plan,
        source_metadata=None,
        date_increment_seconds=1,
    )

    messages = [commit.message.strip() for commit in repo.iter_commits('HEAD', max_count=2)]

    assert messages == ['feat: descendant change', 'split: target rewrite']
    assert (Path(repo.working_tree_dir) / 'note.txt').read_text(encoding='utf-8') == 'after\n'


def test_rewrite_historical_commit_preserves_author_and_dates_with_real_agent(tmp_path):
    repo, target_dates = _init_repo_with_preserved_metadata_target(tmp_path)
    target_commit = repo.commit('HEAD~1')
    result = SimpleNamespace(
        final_groups=[
            SimpleNamespace(
                group_id=1,
                files=['app.py'],
                commit_message='split: app',
                blocks=[SimpleNamespace(file_path='app.py', start_line=1, end_line=1, kind='hunk')],
            ),
            SimpleNamespace(
                group_id=2,
                files=['lib.py'],
                commit_message='split: lib',
                blocks=[SimpleNamespace(file_path='lib.py', start_line=1, end_line=1, kind='hunk')],
            ),
        ]
    )
    source_metadata = extract_commit_metadata(repo, target_commit.hexsha)
    agent = _make_lightweight_agent(repo)
    rewrite_plan = _build_head_rewrite_plan(agent, target_commit.hexsha, result)

    _rewrite_historical_commit(
        agent,
        target_commit.hexsha,
        result,
        rewrite_plan,
        source_metadata=source_metadata,
        date_increment_seconds=5,
    )

    commits = list(repo.iter_commits('HEAD', max_count=3))
    messages = [commit.message.strip() for commit in commits]

    assert messages == ['feat: descendant change', 'split: lib', 'split: app']
    assert (Path(repo.working_tree_dir) / 'note.txt').read_text(encoding='utf-8') == 'after\n'

    first_rewritten = commits[2]
    second_rewritten = commits[1]

    assert first_rewritten.author.name == 'Original Author'
    assert first_rewritten.author.email == 'author@example.com'
    assert first_rewritten.committer.name == 'Original Committer'
    assert first_rewritten.committer.email == 'committer@example.com'
    assert first_rewritten.authored_datetime == target_dates['author_date']
    assert first_rewritten.committed_datetime == target_dates['commit_date']

    assert second_rewritten.author.name == 'Original Author'
    assert second_rewritten.author.email == 'author@example.com'
    assert second_rewritten.committer.name == 'Original Committer'
    assert second_rewritten.committer.email == 'committer@example.com'
    assert second_rewritten.authored_datetime == offset_datetime(target_dates['author_date'], 5)
    assert second_rewritten.committed_datetime == offset_datetime(target_dates['commit_date'], 5)


def test_rewrite_head_commit_supports_same_file_multiple_groups(tmp_path):
    repo = _init_repo_with_two_hunks_same_file(tmp_path)
    target_commit = repo.head.commit
    result = SimpleNamespace(
        final_groups=[
            SimpleNamespace(
                group_id=1,
                files=['app.py'],
                commit_message='split: first hunk',
                blocks=[SimpleNamespace(file_path='app.py', start_line=2, end_line=2, kind='hunk')],
            ),
            SimpleNamespace(
                group_id=2,
                files=['app.py'],
                commit_message='split: second hunk',
                blocks=[SimpleNamespace(file_path='app.py', start_line=5, end_line=5, kind='hunk')],
            ),
        ]
    )
    agent = _make_lightweight_agent(repo)
    head_rewrite_plan = _build_head_rewrite_plan(agent, target_commit.hexsha, result)

    _rewrite_head_commit(
        agent,
        target_commit.hexsha,
        result,
        head_rewrite_plan,
        source_metadata=None,
        date_increment_seconds=1,
    )

    messages = [commit.message.strip() for commit in repo.iter_commits('HEAD', max_count=2)]
    assert messages == ['split: second hunk', 'split: first hunk']
    assert (Path(repo.working_tree_dir) / 'app.py').read_text(encoding='utf-8') == (
        "def first():\n    return 10\n\n\ndef second():\n    return 20\n"
    )


def test_rewrite_head_commit_supports_deletion(tmp_path):
    repo = _init_repo_with_deleted_file_target(tmp_path)
    target_commit = repo.head.commit
    result = SimpleNamespace(
        final_groups=[
            SimpleNamespace(
                group_id=1,
                files=['delete.txt'],
                commit_message='split: remove file',
                blocks=[SimpleNamespace(file_path='delete.txt', start_line=0, end_line=0, kind='removal')],
            )
        ]
    )
    agent = _make_lightweight_agent(repo)
    head_rewrite_plan = _build_head_rewrite_plan(agent, target_commit.hexsha, result)

    _rewrite_head_commit(
        agent,
        target_commit.hexsha,
        result,
        head_rewrite_plan,
        source_metadata=None,
        date_increment_seconds=1,
    )

    assert not (Path(repo.working_tree_dir) / 'delete.txt').exists()
    assert repo.head.commit.message.strip() == 'split: remove file'


def test_rewrite_head_commit_rolls_back_after_partial_failure(tmp_path):
    repo = _init_repo_with_two_hunks_same_file(tmp_path)
    original_head = repo.head.commit.hexsha
    target_commit = repo.head.commit
    result = SimpleNamespace(
        final_groups=[
            SimpleNamespace(
                group_id=1,
                files=['app.py'],
                commit_message='split: first hunk',
                blocks=[SimpleNamespace(file_path='app.py', start_line=2, end_line=2, kind='hunk')],
            ),
            SimpleNamespace(
                group_id=2,
                files=['app.py'],
                commit_message='split: second hunk',
                blocks=[SimpleNamespace(file_path='app.py', start_line=5, end_line=5, kind='hunk')],
            ),
        ]
    )
    agent = _make_lightweight_agent(repo)
    head_rewrite_plan = _build_head_rewrite_plan(agent, target_commit.hexsha, result)

    calls = {'count': 0}
    original_commit = agent.commit_staged_changes

    def flaky_commit(*args, **kwargs):
        calls['count'] += 1
        if calls['count'] == 2:
            raise RuntimeError('boom')
        return original_commit(*args, **kwargs)

    agent.commit_staged_changes = flaky_commit

    try:
        _rewrite_head_commit(
            agent,
            target_commit.hexsha,
            result,
            head_rewrite_plan,
            source_metadata=None,
            date_increment_seconds=1,
        )
    except RuntimeError as exc:
        assert 'boom' in str(exc)
    else:
        raise AssertionError('expected rewrite failure')

    assert repo.head.commit.hexsha == original_head
    assert not repo.is_dirty(untracked_files=False)


def test_rewrite_historical_commit_supports_same_file_multiple_groups(tmp_path):
    repo = _init_repo_with_historical_same_file_target(tmp_path)
    target_commit = repo.commit('HEAD~1')
    result = SimpleNamespace(
        final_groups=[
            SimpleNamespace(
                group_id=1,
                files=['app.py'],
                commit_message='split: first hunk',
                blocks=[SimpleNamespace(file_path='app.py', start_line=2, end_line=2, kind='hunk')],
            ),
            SimpleNamespace(
                group_id=2,
                files=['app.py'],
                commit_message='split: second hunk',
                blocks=[SimpleNamespace(file_path='app.py', start_line=5, end_line=5, kind='hunk')],
            ),
        ]
    )
    agent = _make_lightweight_agent(repo)
    rewrite_plan = _build_head_rewrite_plan(agent, target_commit.hexsha, result)

    _rewrite_historical_commit(
        agent,
        target_commit.hexsha,
        result,
        rewrite_plan,
        source_metadata=None,
        date_increment_seconds=1,
    )

    messages = [commit.message.strip() for commit in repo.iter_commits('HEAD', max_count=3)]
    assert messages == ['feat: descendant change', 'split: second hunk', 'split: first hunk']
    assert (Path(repo.working_tree_dir) / 'app.py').read_text(encoding='utf-8') == (
        "def first():\n    return 10\n\n\ndef second():\n    return 20\n"
    )


def test_rewrite_historical_commit_supports_deletion(tmp_path):
    repo = _init_repo_with_historical_deleted_target(tmp_path)
    target_commit = repo.commit('HEAD~1')
    result = SimpleNamespace(
        final_groups=[
            SimpleNamespace(
                group_id=1,
                files=['delete.txt'],
                commit_message='split: remove file',
                blocks=[SimpleNamespace(file_path='delete.txt', start_line=0, end_line=0, kind='removal')],
            )
        ]
    )
    agent = _make_lightweight_agent(repo)
    rewrite_plan = _build_head_rewrite_plan(agent, target_commit.hexsha, result)

    _rewrite_historical_commit(
        agent,
        target_commit.hexsha,
        result,
        rewrite_plan,
        source_metadata=None,
        date_increment_seconds=1,
    )

    messages = [commit.message.strip() for commit in repo.iter_commits('HEAD', max_count=2)]
    assert messages == ['feat: descendant change', 'split: remove file']
    assert not (Path(repo.working_tree_dir) / 'delete.txt').exists()


def _make_lightweight_agent(repo: Repo):
    CommitGroupingAgent = _load_commit_grouping_agent()
    agent = CommitGroupingAgent.__new__(CommitGroupingAgent)
    agent.repo = repo
    agent.repo_root = Path(repo.working_tree_dir)
    return agent


def _load_commit_grouping_agent():
    if 'groupit.core.agent' in sys.modules:
        return sys.modules['groupit.core.agent'].CommitGroupingAgent

    original_pipeline = sys.modules.get('groupit.core.pipeline')
    stub_pipeline = types.ModuleType('groupit.core.pipeline')

    class DummyPipeline:
        def __init__(self, *args, **kwargs):
            return None

    stub_pipeline.CommitGroupingPipeline = DummyPipeline
    sys.modules['groupit.core.pipeline'] = stub_pipeline

    try:
        module = importlib.import_module('groupit.core.agent')
        return module.CommitGroupingAgent
    finally:
        if original_pipeline is not None:
            sys.modules['groupit.core.pipeline'] = original_pipeline
        else:
            sys.modules.pop('groupit.core.pipeline', None)


def _init_repo_with_target_and_descendant(tmp_path: Path) -> Repo:
    repo_path = tmp_path / 'repo'
    repo_path.mkdir()

    repo = Repo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value('user', 'name', 'Test User')
        config.set_value('user', 'email', 'test@example.com')

    app_file = repo_path / 'app.py'
    app_file.write_text("print('base')\n", encoding='utf-8')
    repo.index.add(['app.py'])
    repo.index.commit('feat: base')

    app_file.write_text("print('target')\n", encoding='utf-8')
    repo.index.add(['app.py'])
    repo.index.commit('feat: target change')

    note_file = repo_path / 'note.txt'
    note_file.write_text('after\n', encoding='utf-8')
    repo.index.add(['note.txt'])
    repo.index.commit('feat: descendant change')

    return repo


def _init_repo_with_preserved_metadata_target(tmp_path: Path):
    repo_path = tmp_path / 'repo'
    repo_path.mkdir()

    repo = Repo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value('user', 'name', 'Current User')
        config.set_value('user', 'email', 'current@example.com')

    app_file = repo_path / 'app.py'
    lib_file = repo_path / 'lib.py'
    app_file.write_text("print('base app')\n", encoding='utf-8')
    lib_file.write_text("print('base lib')\n", encoding='utf-8')
    repo.index.add(['app.py', 'lib.py'])
    repo.index.commit('feat: base')

    app_file.write_text("print('target app')\n", encoding='utf-8')
    lib_file.write_text("print('target lib')\n", encoding='utf-8')
    repo.index.add(['app.py', 'lib.py'])

    author = Actor('Original Author', 'author@example.com')
    committer = Actor('Original Committer', 'committer@example.com')
    author_date = datetime(2026, 3, 12, 10, 34, 11, tzinfo=timezone.utc)
    commit_date = datetime(2026, 3, 12, 10, 34, 21, tzinfo=timezone.utc)
    repo.index.commit(
        'feat: target change',
        author=author,
        committer=committer,
        author_date=author_date,
        commit_date=commit_date,
    )

    note_file = repo_path / 'note.txt'
    note_file.write_text('after\n', encoding='utf-8')
    repo.index.add(['note.txt'])
    repo.index.commit('feat: descendant change')

    return repo, {'author_date': author_date, 'commit_date': commit_date}


def _init_repo_with_two_hunks_same_file(tmp_path: Path) -> Repo:
    repo_path = tmp_path / 'repo'
    repo_path.mkdir()

    repo = Repo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value('user', 'name', 'Test User')
        config.set_value('user', 'email', 'test@example.com')

    app_file = repo_path / 'app.py'
    app_file.write_text(
        "def first():\n    return 1\n\n\ndef second():\n    return 2\n",
        encoding='utf-8',
    )
    repo.index.add(['app.py'])
    repo.index.commit('feat: base')

    app_file.write_text(
        "def first():\n    return 10\n\n\ndef second():\n    return 20\n",
        encoding='utf-8',
    )
    repo.index.add(['app.py'])
    repo.index.commit('feat: target change')

    return repo


def _init_repo_with_deleted_file_target(tmp_path: Path) -> Repo:
    repo_path = tmp_path / 'repo'
    repo_path.mkdir()

    repo = Repo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value('user', 'name', 'Test User')
        config.set_value('user', 'email', 'test@example.com')

    delete_file = repo_path / 'delete.txt'
    delete_file.write_text('remove me\n', encoding='utf-8')
    repo.index.add(['delete.txt'])
    repo.index.commit('feat: base')

    delete_file.unlink()
    repo.index.remove(['delete.txt'])
    repo.index.commit('feat: delete file')

    return repo


def _init_repo_with_historical_same_file_target(tmp_path: Path) -> Repo:
    repo = _init_repo_with_two_hunks_same_file(tmp_path)
    note_file = Path(repo.working_tree_dir) / 'note.txt'
    note_file.write_text('after\n', encoding='utf-8')
    repo.index.add(['note.txt'])
    repo.index.commit('feat: descendant change')
    return repo


def _init_repo_with_historical_deleted_target(tmp_path: Path) -> Repo:
    repo = _init_repo_with_deleted_file_target(tmp_path)
    note_file = Path(repo.working_tree_dir) / 'note.txt'
    note_file.write_text('after\n', encoding='utf-8')
    repo.index.add(['note.txt'])
    repo.index.commit('feat: descendant change')
    return repo
