import json

from groupit.auth import AuthService
import groupit.config.settings as settings_module


class FakeStore:
    def __init__(self):
        self.data = {}

    def get(self, provider):
        return self.data.get(provider)

    def set(self, provider, credential):
        self.data[provider] = credential

    def delete(self, provider):
        self.data.pop(provider, None)


def reset_settings(tmp_path, monkeypatch):
    config_path = tmp_path / 'config' / 'groupit.json'
    monkeypatch.setattr(settings_module, 'get_default_config_path', lambda: config_path)
    settings_module._settings = None
    settings_module.get_settings.cache_clear()
    return config_path


def test_auth_service_resolve_precedence(tmp_path, monkeypatch):
    reset_settings(tmp_path, monkeypatch)
    store = FakeStore()
    store.set('openai', 'stored-key')
    service = AuthService(store=store)

    monkeypatch.setenv('OPENAI_API_KEY', 'env-key')

    explicit = service.resolve('openai', explicit_api_key='explicit-key')
    assert explicit.source == 'explicit'
    assert explicit.credential == 'explicit-key'

    env = service.resolve('openai')
    assert env.source == 'env'
    assert env.credential == 'env-key'

    monkeypatch.delenv('OPENAI_API_KEY')
    stored = service.resolve('openai')
    assert stored.source == 'stored'
    assert stored.credential == 'stored-key'


def test_auth_service_inspect_reports_active_source_and_availability(tmp_path, monkeypatch):
    reset_settings(tmp_path, monkeypatch)
    store = FakeStore()
    store.set('gemini', 'stored-key')
    service = AuthService(store=store)

    monkeypatch.setenv('GEMINI_API_KEY', 'env-key')

    inspection = service.inspect('gemini')
    assert inspection.active_source == 'env'
    assert inspection.stored_available is True
    assert inspection.env_available is True


def test_auth_login_persists_metadata_without_secret(tmp_path, monkeypatch):
    config_path = reset_settings(tmp_path, monkeypatch)
    service = AuthService(store=FakeStore())
    monkeypatch.setattr(service, '_clear_provider_cache', lambda: None)
    monkeypatch.setattr(service, '_validate_direct', lambda provider, credential: (True, 'provider validation succeeded'))

    result = service.login('openai', 'super-secret', validate=True)

    assert result.source == 'stored'
    assert result.validation_state == 'verified'

    saved = json.loads(config_path.read_text(encoding='utf-8'))
    assert saved['auth']['providers']['openai']['validation_state'] == 'verified'
    assert 'super-secret' not in json.dumps(saved)


def test_auth_login_overwrite_resets_to_unverified_before_validation(tmp_path, monkeypatch):
    reset_settings(tmp_path, monkeypatch)
    store = FakeStore()
    service = AuthService(store=store)
    monkeypatch.setattr(service, '_clear_provider_cache', lambda: None)

    states = []

    def fake_validate(provider, credential):
        current = service._get_provider_metadata(provider)['validation_state']
        states.append(current)
        return True, 'provider validation succeeded'

    monkeypatch.setattr(service, '_validate_direct', fake_validate)

    service.login('openai', 'first-key', validate=True)
    service.login('openai', 'second-key', validate=True)

    assert states == ['unverified', 'unverified']
