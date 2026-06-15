import pytest
from cryptography.fernet import Fernet

from app.security import secrets
from app.security.secrets import (
    SECRET_PREFIX,
    SecretConfigurationError,
    decrypt_secret,
    encrypt_secret,
    is_encrypted_secret,
    mask_secret,
)


def test_encrypt_secret_stores_ciphertext(monkeypatch):
    monkeypatch.setenv(secrets.SECRET_KEY_ENV, Fernet.generate_key().decode("utf-8"))

    encrypted = encrypt_secret("test-provider-key")

    assert encrypted.startswith(SECRET_PREFIX)
    assert "test-provider-key" not in encrypted
    assert decrypt_secret(encrypted) == "test-provider-key"


def test_decrypt_secret_allows_legacy_plaintext():
    assert decrypt_secret("legacy-provider-key") == "legacy-provider-key"
    assert not is_encrypted_secret("legacy-provider-key")


def test_encrypt_secret_requires_configured_key(monkeypatch):
    monkeypatch.delenv(secrets.SECRET_KEY_ENV, raising=False)

    with pytest.raises(SecretConfigurationError):
        encrypt_secret("test-provider-key")


def test_mask_secret_never_exposes_full_value(monkeypatch):
    monkeypatch.setenv(secrets.SECRET_KEY_ENV, Fernet.generate_key().decode("utf-8"))
    encrypted = encrypt_secret("test-provider-key")

    assert mask_secret(encrypted) == "test****-key"
    assert mask_secret("short") == "****"

