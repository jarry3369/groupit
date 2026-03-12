from pathlib import Path

from git import Repo

from groupit.core.git_operations import materialize_commit_tree


def test_materialize_commit_tree_uses_target_commit_contents(tmp_path):
    repo = _init_repo_with_descendant_change(tmp_path)
    target_commit = repo.commit('HEAD~1')
    snapshot_root = tmp_path / 'snapshot'
    snapshot_root.mkdir()

    materialize_commit_tree(repo, target_commit.hexsha, snapshot_root)

    assert (snapshot_root / 'app.py').read_text(encoding='utf-8') == "def value():\n    return 2\n"
    assert (Path(repo.working_tree_dir) / 'app.py').read_text(encoding='utf-8') == "def value():\n    return 3\n"


def _init_repo_with_descendant_change(tmp_path: Path) -> Repo:
    repo_path = tmp_path / 'repo'
    repo_path.mkdir()

    repo = Repo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value('user', 'name', 'Test User')
        config.set_value('user', 'email', 'test@example.com')

    app_file = repo_path / 'app.py'
    app_file.write_text("def value():\n    return 1\n", encoding='utf-8')
    repo.index.add(['app.py'])
    repo.index.commit('feat: base')

    app_file.write_text("def value():\n    return 2\n", encoding='utf-8')
    repo.index.add(['app.py'])
    repo.index.commit('feat: target')

    app_file.write_text("def value():\n    return 3\n", encoding='utf-8')
    repo.index.add(['app.py'])
    repo.index.commit('feat: descendant')

    return repo
