import groupit.cli.commands.validate as validate_module
from groupit.auth.service import AuthInspection, AuthResolution


class StubAuthService:
    def inspect(self, provider):
        if provider == 'openai':
            return AuthInspection(
                provider=provider,
                active_source='stored',
                stored_available=True,
                env_available=False,
                requires_auth=True,
                validation_state='verified',
                diagnostic='stored credential found in keyring',
            )
        return AuthInspection(
            provider=provider,
            active_source='not-required',
            stored_available=False,
            env_available=False,
            requires_auth=False,
            validation_state='not-required',
            diagnostic='provider does not require authentication',
        )

    def validate_active(self, provider, explicit_api_key=None):
        return True, AuthResolution(
            provider=provider,
            credential='stored-key' if provider == 'openai' else None,
            source='stored' if provider == 'openai' else 'not-required',
            requires_auth=provider != 'ollama',
            validation_state='verified' if provider == 'openai' else 'not-required',
            diagnostic='provider validation succeeded',
        )

    def format_validation_label(self, validation_state):
        return validation_state


def test_validate_llm_providers_uses_shared_auth_service(monkeypatch):
    monkeypatch.setattr(validate_module, 'AuthService', lambda: StubAuthService())
    monkeypatch.setattr(validate_module, 'console', type('DummyConsole', (), {'print': lambda *args, **kwargs: None})())

    import groupit.llm as llm_module

    monkeypatch.setattr(llm_module, '__getattr__', lambda name: (lambda: ['openai', 'ollama']) if name == 'get_available_providers' else None)
    monkeypatch.setattr(validate_module, 'get_available_providers', lambda: ['openai', 'ollama'], raising=False)

    assert validate_module._validate_llm_providers() is True
