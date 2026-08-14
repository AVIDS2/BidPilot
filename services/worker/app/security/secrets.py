"""Application-level encryption helpers for user-supplied secrets."""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken

SECRET_PREFIX = "enc:v1:"
SECRET_KEY_ENV = "DOCPILOT_SECRETS_KEY"


class SecretConfigurationError(RuntimeError):
    """Raised when secret encryption is requested without a valid key."""


class SecretDecryptionError(RuntimeError):
    """Raised when an encrypted secret cannot be decrypted."""


def _fernet() -> Fernet:
    key = os.environ.get(SECRET_KEY_ENV)
    if not key:
        raise SecretConfigurationError(f"{SECRET_KEY_ENV} is required to store provider API keys")
    try:
        return Fernet(key.encode("utf-8"))
    except ValueError as exc:
        raise SecretConfigurationError(f"{SECRET_KEY_ENV} must be a valid Fernet key") from exc


def is_encrypted_secret(value: str | None) -> bool:
    return bool(value and value.startswith(SECRET_PREFIX))


def encrypt_secret(value: str) -> str:
    """Encrypt a plaintext secret unless it is already encrypted."""
    if is_encrypted_secret(value):
        return value
    token = _fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{SECRET_PREFIX}{token}"


def decrypt_secret(value: str) -> str:
    """Decrypt an encrypted secret, while allowing legacy plaintext rows."""
    if not is_encrypted_secret(value):
        return value
    token = value[len(SECRET_PREFIX):]
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, SecretConfigurationError) as exc:
        raise SecretDecryptionError("Provider API key cannot be decrypted") from exc


def mask_secret(value: str) -> str:
    """Return a non-sensitive display form without leaking encrypted payloads."""
    if is_encrypted_secret(value):
        try:
            value = decrypt_secret(value)
        except SecretDecryptionError:
            return "****encrypted"
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"
