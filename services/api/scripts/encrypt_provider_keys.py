"""Encrypt legacy plaintext provider API keys in-place.

Run from the repository root with:
uv run --directory services/api python scripts/encrypt_provider_keys.py
"""

from __future__ import annotations

from app.db import SessionLocal
from app.models import ProviderConfig
from app.security.secrets import encrypt_secret, is_encrypted_secret


def main() -> int:
    updated = 0
    with SessionLocal() as db:
        configs = db.query(ProviderConfig).all()
        for config in configs:
            if is_encrypted_secret(config.api_key):
                continue
            config.api_key = encrypt_secret(config.api_key)
            updated += 1
        db.commit()

    print(f"encrypted_provider_keys={updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

