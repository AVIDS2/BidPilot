"""Create a dedicated local PostgreSQL test database without printing its DSN."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


LOCAL_HOSTS = {"", "localhost", "127.0.0.1", "::1"}


def normalize_postgres_driver(source_url: str):
    """Use the project's installed psycopg v3 driver for plain PostgreSQL URLs."""
    url = make_url(source_url)
    if url.drivername == "postgresql":
        return url.set(drivername="postgresql+psycopg")
    return url


def main() -> int:
    source_url = os.environ.get("DOCPILOT_DATABASE_URL", "")
    if not source_url:
        api_root = Path(__file__).resolve().parents[1] / "services" / "api"
        if str(api_root) not in sys.path:
            sys.path.insert(0, str(api_root))
        try:
            from app.db import DATABASE_URL
        except ImportError:
            print("DOCPILOT_DATABASE_URL is required to derive a local test database", file=sys.stderr)
            return 2
        source_url = DATABASE_URL

    url = normalize_postgres_driver(source_url)
    if not url.drivername.startswith("postgresql") or url.host not in LOCAL_HOSTS:
        print("Refusing to create a test database on a non-local PostgreSQL host", file=sys.stderr)
        return 2
    if not url.database:
        print("DOCPILOT_DATABASE_URL must include a database name", file=sys.stderr)
        return 2

    test_name = url.database if url.database.endswith("_test") else f"{url.database}_test"
    if not re.fullmatch(r"[A-Za-z0-9_]+", test_name):
        print("Derived test database name is invalid", file=sys.stderr)
        return 2

    admin_url = url.set(database="postgres")
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": test_name},
            )
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{test_name}"'))
    finally:
        engine.dispose()

    print(f"Prepared local test database '{test_name}'.")
    print("Set DOCPILOT_TEST_DATABASE_URL to the same connection with that database name.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
