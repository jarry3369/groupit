import os

from groupit.config.settings import get_settings


def test_git_settings_load_from_env(monkeypatch):
    monkeypatch.setenv('GROUPIT_GIT_PRESERVE_METADATA', 'true')
    monkeypatch.setenv('GROUPIT_GIT_PRESERVE_DATE', 'single')
    monkeypatch.setenv('GROUPIT_GIT_DATE_INCREMENT', '7')
    monkeypatch.setenv('GROUPIT_GIT_GPG_SIGN_KEY', 'ABC123')
    get_settings.cache_clear()

    settings = get_settings(force_reload=True)

    assert settings.git.preserve_metadata_by_default is True
    assert settings.git.preserve_date_mode == 'single'
    assert settings.git.date_increment_seconds == 7
    assert settings.git.gpg_sign_key == 'ABC123'

    get_settings.cache_clear()
