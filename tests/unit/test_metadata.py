from pathlib import Path
from datetime import datetime

from git import Repo

from groupit.core.metadata import (
    apply_metadata_overrides,
    build_preserved_commit_kwargs,
    extract_commit_metadata,
    metadata_from_repo_defaults,
    offset_datetime,
)


def test_extract_commit_metadata_reads_author_and_dates(tmp_path):
    repo = _init_repo(tmp_path)
    commit = repo.head.commit

    metadata = extract_commit_metadata(repo, commit.hexsha)

    assert metadata.author_name == 'Test User'
    assert metadata.author_email == 'test@example.com'
    assert metadata.committer_name == 'Test User'
    assert metadata.committer_email == 'test@example.com'
    assert metadata.authored_date
    assert metadata.committed_date


def test_offset_datetime_increments_seconds():
    assert offset_datetime(datetime(2026, 3, 12, 12, 0, 0), 5) == datetime(2026, 3, 12, 12, 0, 5)


def test_build_preserved_commit_kwargs_uses_commit_date_key(tmp_path):
    repo = _init_repo(tmp_path)
    metadata = extract_commit_metadata(repo, repo.head.commit.hexsha)

    kwargs = build_preserved_commit_kwargs(metadata, commit_index=1, date_increment_seconds=5)

    assert 'author' in kwargs
    assert 'committer' in kwargs
    assert 'author_date' in kwargs
    assert 'commit_date' in kwargs
    assert 'committer_date' not in kwargs
    assert kwargs['author_date'] > metadata.authored_date
    assert kwargs['commit_date'] > metadata.committed_date


def test_build_preserved_commit_kwargs_single_mode_only_preserves_first(tmp_path):
    repo = _init_repo(tmp_path)
    metadata = extract_commit_metadata(repo, repo.head.commit.hexsha)

    first_kwargs = build_preserved_commit_kwargs(metadata, commit_index=0, date_increment_seconds=5, preserve_date_mode='single')
    later_kwargs = build_preserved_commit_kwargs(metadata, commit_index=1, date_increment_seconds=5, preserve_date_mode='single')

    assert 'author_date' in first_kwargs
    assert 'commit_date' in first_kwargs
    assert 'author_date' not in later_kwargs
    assert 'commit_date' not in later_kwargs


def test_apply_metadata_overrides_replaces_fields(tmp_path):
    repo = _init_repo(tmp_path)
    metadata = extract_commit_metadata(repo, repo.head.commit.hexsha)

    updated = apply_metadata_overrides(
        metadata,
        author_name='Override Author',
        committer_email='override@example.com',
        author_date='2026-03-12T12:00:00+00:00',
    )

    assert updated.author_name == 'Override Author'
    assert updated.committer_email == 'override@example.com'
    assert updated.authored_date.isoformat() == '2026-03-12T12:00:00+00:00'


def test_metadata_from_repo_defaults_uses_repo_identity(tmp_path):
    repo = _init_repo(tmp_path)

    metadata = metadata_from_repo_defaults(repo)

    assert metadata.author_name == 'Test User'
    assert metadata.author_email == 'test@example.com'
    assert metadata.committer_name == 'Test User'
    assert metadata.committer_email == 'test@example.com'


def _init_repo(tmp_path: Path) -> Repo:
    repo_path = tmp_path / 'repo'
    repo_path.mkdir()

    repo = Repo.init(repo_path)
    with repo.config_writer() as config:
        config.set_value('user', 'name', 'Test User')
        config.set_value('user', 'email', 'test@example.com')

    tracked_file = repo_path / 'note.txt'
    tracked_file.write_text('hello\n', encoding='utf-8')
    repo.index.add(['note.txt'])
    repo.index.commit('feat: initial note')

    return repo
