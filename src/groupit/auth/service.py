"""
Shared auth resolution and metadata management.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..config import get_settings
from ..constants import KNOWN_LLM_PROVIDERS
from .store import CredentialStore, KeyringCredentialStore


VALIDATION_STATE_LABELS = {
    'verified': 'verified',
    'unverified': 'unverified',
    'failed': 'last validation failed',
    'not-required': 'not required',
}


@dataclass
class AuthResolution:
    provider: str
    credential: Optional[str]
    source: str
    requires_auth: bool
    validation_state: str
    diagnostic: str


@dataclass
class AuthInspection:
    provider: str
    active_source: str
    stored_available: bool
    env_available: bool
    requires_auth: bool
    validation_state: str
    diagnostic: str


class AuthService:
    """Resolve provider credentials and manage auth metadata."""

    def __init__(self, store: Optional[CredentialStore] = None):
        self.store = store or KeyringCredentialStore()

    def resolve(self, provider: str, explicit_api_key: Optional[str] = None) -> AuthResolution:
        provider = self._normalize_provider(provider)
        requires_auth = self._requires_auth(provider)

        if not requires_auth:
            return AuthResolution(
                provider=provider,
                credential=None,
                source='not-required',
                requires_auth=False,
                validation_state='not-required',
                diagnostic='provider does not require authentication',
            )

        metadata = self._get_provider_metadata(provider)
        env_var_name = self._env_var_name(provider)
        env_value = os.getenv(env_var_name)
        stored_credential = self._get_stored_credential(provider)

        if explicit_api_key:
            return AuthResolution(
                provider=provider,
                credential=explicit_api_key,
                source='explicit',
                requires_auth=True,
                validation_state=self._metadata_validation_state(metadata),
                diagnostic='using explicit API key override',
            )

        if env_value:
            return AuthResolution(
                provider=provider,
                credential=env_value,
                source='env',
                requires_auth=True,
                validation_state=self._metadata_validation_state(metadata),
                diagnostic=f'environment variable {env_var_name} is set',
            )

        if stored_credential:
            return AuthResolution(
                provider=provider,
                credential=stored_credential,
                source='stored',
                requires_auth=True,
                validation_state=self._metadata_validation_state(metadata),
                diagnostic='stored credential found in keyring',
            )

        return AuthResolution(
            provider=provider,
            credential=None,
            source='none',
            requires_auth=True,
            validation_state=self._metadata_validation_state(metadata),
            diagnostic=(
                f'no credential found; run `groupit auth login {provider}` '
                f'or set {env_var_name}'
            ),
        )

    def inspect(self, provider: str) -> AuthInspection:
        resolution = self.resolve(provider)
        return AuthInspection(
            provider=provider,
            active_source=resolution.source,
            stored_available=self._get_stored_credential(provider) is not None,
            env_available=bool(os.getenv(self._env_var_name(provider))),
            requires_auth=resolution.requires_auth,
            validation_state=resolution.validation_state,
            diagnostic=resolution.diagnostic,
        )

    def login(
        self,
        provider: str,
        credential: str,
        validate: bool = True,
    ) -> AuthResolution:
        provider = self._normalize_provider(provider)
        if not self._requires_auth(provider):
            self._clear_provider_cache()
            return self.resolve(provider)

        self.store.set(provider, credential)
        self._update_provider_metadata(
            provider,
            last_login_at=self._now_iso(),
            validation_state='unverified',
            diagnostic='stored credential found in keyring',
        )
        self._clear_provider_cache()

        if not validate:
            return self.resolve(provider)

        is_valid, diagnostic = self._validate_direct(provider, credential)
        self._update_provider_metadata(
            provider,
            validation_state='verified' if is_valid else 'failed',
            diagnostic=diagnostic,
            last_validated_at=self._now_iso(),
        )
        return self.resolve(provider)

    def logout(self, provider: str) -> None:
        provider = self._normalize_provider(provider)
        if self._requires_auth(provider):
            self.store.delete(provider)
        self._delete_provider_metadata(provider)
        self._clear_provider_cache()

    def validate_active(self, provider: str, explicit_api_key: Optional[str] = None) -> tuple[bool, AuthResolution]:
        resolution = self.resolve(provider, explicit_api_key=explicit_api_key)
        if not resolution.requires_auth:
            return True, resolution

        if resolution.credential is None:
            return False, resolution

        is_valid, diagnostic = self._validate_direct(provider, resolution.credential)

        # Persist validation only for non-explicit credentials.
        if resolution.source != 'explicit':
            self._update_provider_metadata(
                provider,
                validation_state='verified' if is_valid else 'failed',
                diagnostic=diagnostic,
                last_validated_at=self._now_iso(),
            )

        updated = self.resolve(provider, explicit_api_key=explicit_api_key)
        if resolution.source == 'explicit':
            updated = AuthResolution(
                provider=updated.provider,
                credential=updated.credential,
                source=updated.source,
                requires_auth=updated.requires_auth,
                validation_state='verified' if is_valid else 'failed',
                diagnostic=diagnostic,
            )

        return is_valid, updated

    def format_validation_label(self, validation_state: str) -> str:
        """Return a user-facing label for validation state."""
        return VALIDATION_STATE_LABELS.get(validation_state, validation_state)

    def available_providers(self) -> list[str]:
        """Return the supported auth provider list."""
        return list(KNOWN_LLM_PROVIDERS)

    def _validate_direct(self, provider: str, credential: str) -> tuple[bool, str]:
        if not self._requires_auth(provider):
            return True, 'provider does not require authentication'

        try:
            from ..llm.providers.registry import create_provider, is_provider_available
        except Exception:
            return False, 'provider validation unavailable'

        if not is_provider_available(provider):
            return False, f'provider {provider} is not available in this environment'

        try:
            candidate = create_provider(provider, credential)
            response = candidate.generate(prompt='Hello', max_tokens=5, temperature=0.0)
            if response.content:
                return True, 'provider validation succeeded'
            return False, 'provider validation returned an empty response'
        except Exception:
            return False, 'provider validation failed'

    def _normalize_provider(self, provider: str) -> str:
        if provider not in KNOWN_LLM_PROVIDERS:
            raise ValueError(
                f"Unknown provider '{provider}'. Available providers: {', '.join(KNOWN_LLM_PROVIDERS)}"
            )
        return provider

    def _requires_auth(self, provider: str) -> bool:
        return provider != 'ollama'

    def _env_var_name(self, provider: str) -> str:
        return f'{provider.upper()}_API_KEY'

    def _get_stored_credential(self, provider: str) -> Optional[str]:
        if not self._requires_auth(provider):
            return None
        try:
            return self.store.get(provider)
        except Exception:
            return None

    def _provider_metadata_map(self) -> Dict[str, Dict[str, Any]]:
        settings = get_settings()
        providers = settings.auth.setdefault('providers', {})
        return providers

    def _get_provider_metadata(self, provider: str) -> Dict[str, Any]:
        return dict(self._provider_metadata_map().get(provider, {}))

    def _update_provider_metadata(self, provider: str, **updates: Any) -> None:
        settings = get_settings()
        providers = settings.auth.setdefault('providers', {})
        provider_meta = dict(providers.get(provider, {}))
        provider_meta.update({key: value for key, value in updates.items() if value is not None})
        providers[provider] = provider_meta
        settings.auth['providers'] = providers
        self._persist_settings(settings)

    def _delete_provider_metadata(self, provider: str) -> None:
        settings = get_settings()
        providers = settings.auth.setdefault('providers', {})
        providers.pop(provider, None)
        settings.auth['providers'] = providers
        self._persist_settings(settings)

    def _persist_settings(self, settings) -> None:
        config_path = settings.config_file or get_settings(force_reload=False).config_file
        if config_path is None:
            return
        settings.config_file = config_path
        settings.save_to_file(config_path)

    def _metadata_validation_state(self, metadata: Dict[str, Any]) -> str:
        return metadata.get('validation_state', 'unverified')

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _clear_provider_cache(self) -> None:
        from ..llm.factory import clear_provider_cache

        clear_provider_cache()


def auth_resolution_to_dict(resolution: AuthResolution) -> Dict[str, Any]:
    """Serialize auth resolution dataclass."""
    return asdict(resolution)


def auth_inspection_to_dict(inspection: AuthInspection) -> Dict[str, Any]:
    """Serialize auth inspection dataclass."""
    return asdict(inspection)
