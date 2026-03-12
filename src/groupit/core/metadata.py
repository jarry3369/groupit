"""
Helpers for extracting and incrementing commit metadata.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from git import Actor


@dataclass(frozen=True)
class CommitMetadata:
    """Minimal commit metadata used for split preservation."""

    author_name: str
    author_email: str
    committer_name: str
    committer_email: str
    authored_date: datetime
    committed_date: datetime


def extract_commit_metadata(repo, commit_hash: str) -> CommitMetadata:
    """Extract author identity and dates from an existing commit."""
    commit = repo.commit(commit_hash)
    return CommitMetadata(
        author_name=commit.author.name,
        author_email=commit.author.email,
        committer_name=commit.committer.name,
        committer_email=commit.committer.email,
        authored_date=commit.authored_datetime,
        committed_date=commit.committed_datetime,
    )


def offset_datetime(value: datetime, seconds: int) -> datetime:
    """Offset a datetime by a number of seconds."""
    return value + timedelta(seconds=seconds)


def parse_datetime_text(value: str) -> datetime:
    """Parse a user-provided datetime string."""
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def metadata_from_repo_defaults(repo) -> CommitMetadata:
    """Build metadata from the current repo user identity and current time."""
    reader = repo.config_reader()
    user_name = reader.get_value('user', 'name', 'GroupIt')
    user_email = reader.get_value('user', 'email', 'groupit@example.com')
    now = datetime.now(timezone.utc)
    return CommitMetadata(
        author_name=user_name,
        author_email=user_email,
        committer_name=user_name,
        committer_email=user_email,
        authored_date=now,
        committed_date=now,
    )


def apply_metadata_overrides(
    metadata: CommitMetadata,
    author_name=None,
    author_email=None,
    author_date=None,
    committer_name=None,
    committer_email=None,
    committer_date=None,
) -> CommitMetadata:
    """Apply optional manual overrides to commit metadata."""
    updates = {}
    if author_name:
        updates['author_name'] = author_name
    if author_email:
        updates['author_email'] = author_email
    if author_date:
        updates['authored_date'] = parse_datetime_text(author_date)
    if committer_name:
        updates['committer_name'] = committer_name
    if committer_email:
        updates['committer_email'] = committer_email
    if committer_date:
        updates['committed_date'] = parse_datetime_text(committer_date)
    return replace(metadata, **updates)


def build_preserved_commit_kwargs(
    metadata: CommitMetadata,
    commit_index: int,
    date_increment_seconds: int,
    preserve_date_mode: str = 'all',
) -> dict:
    """Build GitPython commit kwargs for preserved author/date metadata."""
    seconds_offset = commit_index * date_increment_seconds
    kwargs = {
        'author': Actor(metadata.author_name, metadata.author_email),
        'committer': Actor(metadata.committer_name, metadata.committer_email),
    }
    if preserve_date_mode == 'all':
        kwargs['author_date'] = offset_datetime(metadata.authored_date, seconds_offset)
        kwargs['commit_date'] = offset_datetime(metadata.committed_date, seconds_offset)
    elif preserve_date_mode == 'single' and commit_index == 0:
        kwargs['author_date'] = metadata.authored_date
        kwargs['commit_date'] = metadata.committed_date
    return kwargs


def build_git_env_for_metadata(
    metadata: CommitMetadata,
    commit_index: int,
    date_increment_seconds: int,
    preserve_date_mode: str = 'all',
) -> dict:
    """Build git CLI environment variables for preserved metadata."""
    kwargs = build_preserved_commit_kwargs(
        metadata,
        commit_index,
        date_increment_seconds,
        preserve_date_mode,
    )
    env = {
        'GIT_AUTHOR_NAME': metadata.author_name,
        'GIT_AUTHOR_EMAIL': metadata.author_email,
        'GIT_COMMITTER_NAME': metadata.committer_name,
        'GIT_COMMITTER_EMAIL': metadata.committer_email,
    }
    if 'author_date' in kwargs:
        env['GIT_AUTHOR_DATE'] = kwargs['author_date'].isoformat()
    if 'commit_date' in kwargs:
        env['GIT_COMMITTER_DATE'] = kwargs['commit_date'].isoformat()
    return env
