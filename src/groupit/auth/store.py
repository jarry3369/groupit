"""
Credential storage backends for CLI auth.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


SERVICE_NAME = 'groupit'


class CredentialStoreError(RuntimeError):
    """Base error for credential store operations."""


class CredentialStoreUnavailableError(CredentialStoreError):
    """Raised when the configured credential backend is unavailable."""


class CredentialStore(ABC):
    """Abstract credential store."""

    @abstractmethod
    def get(self, provider: str) -> Optional[str]:
        """Return the stored credential for a provider."""

    @abstractmethod
    def set(self, provider: str, credential: str) -> None:
        """Persist a credential for a provider."""

    @abstractmethod
    def delete(self, provider: str) -> None:
        """Delete the stored credential for a provider."""


class KeyringCredentialStore(CredentialStore):
    """Keyring-backed credential store."""

    def _load_backend(self):
        try:
            import keyring
            from keyring.errors import KeyringError, NoKeyringError
        except ImportError as exc:
            raise CredentialStoreUnavailableError(
                "The 'keyring' package is not installed. "
                "Install dependencies or use environment variables."
            ) from exc

        try:
            backend = keyring.get_keyring()
        except Exception as exc:
            raise CredentialStoreUnavailableError(
                "No usable keyring backend is available."
            ) from exc

        return keyring, KeyringError, NoKeyringError, backend

    def get(self, provider: str) -> Optional[str]:
        keyring, keyring_error, no_keyring_error, _ = self._load_backend()
        try:
            return keyring.get_password(SERVICE_NAME, provider)
        except (keyring_error, no_keyring_error) as exc:
            raise CredentialStoreUnavailableError(
                "Failed to read from keyring."
            ) from exc

    def set(self, provider: str, credential: str) -> None:
        keyring, keyring_error, no_keyring_error, _ = self._load_backend()
        try:
            keyring.set_password(SERVICE_NAME, provider, credential)
        except (keyring_error, no_keyring_error) as exc:
            raise CredentialStoreUnavailableError(
                "Failed to store credential in keyring."
            ) from exc

    def delete(self, provider: str) -> None:
        keyring, keyring_error, no_keyring_error, _ = self._load_backend()
        try:
            existing = keyring.get_password(SERVICE_NAME, provider)
            if existing is None:
                return
            keyring.delete_password(SERVICE_NAME, provider)
        except (keyring_error, no_keyring_error) as exc:
            raise CredentialStoreUnavailableError(
                "Failed to delete credential from keyring."
            ) from exc
