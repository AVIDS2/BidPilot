"""Verify Alembic health against existing and freshly created local test databases."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

from prepare_local_test_database import LOCAL_HOSTS, normalize_postgres_driver  # noqa: E402
from test_database_safety import UnsafeTestDatabaseError, resolve_test_database_url  # noqa: E402


REPOSITORY_ROOT = SCRIPT_DIRECTORY.parent
API_ROOT = REPOSITORY_ROOT / "services" / "api"
_DATABASE_NAME_PATTERN = re.compile(r"[A-Za-z0-9_]+")
_SCRATCH_DATABASE_NAME_PATTERN = re.compile(r"[A-Za-z0-9_]+_migration_[a-f0-9]{12}_test")


def migration_head() -> str:
    config = Config(str(API_ROOT / "alembic.ini"))
    head = ScriptDirectory.from_config(config).get_current_head()
    if head is None:
        raise RuntimeError("Alembic has no migration head")
    return head


def derive_scratch_database_name(source_name: str, *, token: str | None = None) -> str:
    if not source_name.endswith("_test"):
        raise UnsafeTestDatabaseError("Migration health checks require a database ending in _test")
    prefix = source_name.removesuffix("_test")
    if not prefix or not _DATABASE_NAME_PATTERN.fullmatch(prefix):
        raise UnsafeTestDatabaseError("Test database name contains unsupported characters")
    suffix = token or uuid4().hex[:12]
    if not re.fullmatch(r"[a-f0-9]{12}", suffix):
        raise ValueError("Migration scratch token must be 12 lowercase hexadecimal characters")
    return f"{prefix}_migration_{suffix}_test"


def local_test_database_url(database_url: str) -> URL:
    url = normalize_postgres_driver(database_url)
    if not url.drivername.startswith("postgresql") or url.host not in LOCAL_HOSTS:
        raise UnsafeTestDatabaseError("Migration health checks only run against local PostgreSQL test databases")
    if not url.database:
        raise UnsafeTestDatabaseError("Test database URL must include a database name")
    derive_scratch_database_name(url.database)
    return url


def create_scratch_database(source_url: URL) -> URL:
    scratch_name = derive_scratch_database_name(source_url.database or "")
    admin_engine = create_engine(source_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{scratch_name}"'))
    finally:
        admin_engine.dispose()
    return source_url.set(database=scratch_name)


def drop_scratch_database(scratch_url: URL) -> None:
    scratch_name = scratch_url.database or ""
    if not _SCRATCH_DATABASE_NAME_PATTERN.fullmatch(scratch_name):
        raise UnsafeTestDatabaseError("Refusing to drop a database outside the migration scratch namespace")
    admin_engine = create_engine(scratch_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{scratch_name}"'))
    finally:
        admin_engine.dispose()


def migration_environment(database_url: URL) -> dict[str, str]:
    environment = dict(os.environ)
    database_url_value = database_url.render_as_string(hide_password=False)
    environment["DOCPILOT_DATABASE_URL"] = database_url_value
    environment["DOCPILOT_TEST_DATABASE_URL"] = database_url_value
    return environment


def migrate_to_head(database_url: URL) -> None:
    environment = migration_environment(database_url)
    executable_name = "alembic.exe" if os.name == "nt" else "alembic"
    alembic_executable = Path(sys.executable).with_name(executable_name)
    command = [str(alembic_executable) if alembic_executable.exists() else "alembic", "upgrade", "head"]
    completed = subprocess.run(
        command,
        cwd=API_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("Alembic upgrade head failed during migration health verification")


def assert_schema_matches_models(database_url: URL, *, expected_revision: str) -> int:
    if str(API_ROOT) not in sys.path:
        sys.path.insert(0, str(API_ROOT))
    from contracts.db import Base
    import app.models  # noqa: F401

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            available_tables = set(inspect(connection).get_table_names(schema="public"))
    finally:
        engine.dispose()

    if revision != expected_revision:
        raise RuntimeError("Migration health verification did not reach the Alembic head")
    missing_tables = sorted(set(Base.metadata.tables) - available_tables)
    if missing_tables:
        raise RuntimeError("Migration health verification found missing application tables")
    return len(Base.metadata.tables)


def verify_database(database_url: URL, *, expected_revision: str) -> int:
    migrate_to_head(database_url)
    return assert_schema_matches_models(database_url, expected_revision=expected_revision)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify local Alembic migration health without exposing database URLs.")
    parser.add_argument(
        "--keep-scratch",
        action="store_true",
        help="keep the generated local scratch database for manual inspection",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        source_url = local_test_database_url(resolve_test_database_url(os.environ))
        expected_revision = migration_head()
        existing_table_count = verify_database(source_url, expected_revision=expected_revision)
        scratch_url = create_scratch_database(source_url)
    except (UnsafeTestDatabaseError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        scratch_table_count = verify_database(scratch_url, expected_revision=expected_revision)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        if not args.keep_scratch:
            drop_scratch_database(scratch_url)

    print(
        "Migration health check passed: "
        f"head={expected_revision}; existing_model_tables={existing_table_count}; "
        f"fresh_model_tables={scratch_table_count}."
    )
    if args.keep_scratch:
        print(f"Kept local scratch database '{scratch_url.database}' for inspection.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
