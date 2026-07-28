import importlib.util
from pathlib import Path

import pytest


_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "verify_migration_health.py"
_SPEC = importlib.util.spec_from_file_location("verify_migration_health", _SCRIPT_PATH)
assert _SPEC is not None
migration_health = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(migration_health)


def test_derive_scratch_database_name_stays_in_test_namespace() -> None:
    assert (
        migration_health.derive_scratch_database_name("docpilot_test", token="a1b2c3d4e5f6")
        == "docpilot_migration_a1b2c3d4e5f6_test"
    )


@pytest.mark.parametrize("database_name", ["docpilot", "docpilot-test", "_test"])
def test_derive_scratch_database_name_rejects_noncanonical_names(database_name: str) -> None:
    with pytest.raises(migration_health.UnsafeTestDatabaseError):
        migration_health.derive_scratch_database_name(database_name, token="a1b2c3d4e5f6")


def test_local_test_database_url_rejects_non_local_database() -> None:
    with pytest.raises(migration_health.UnsafeTestDatabaseError):
        migration_health.local_test_database_url("postgresql://user:secret@db.internal:5432/docpilot_test")


def test_migration_environment_preserves_the_connection_password_for_the_child_process() -> None:
    database_url = migration_health.normalize_postgres_driver(
        "postgresql://user:fixture-password@localhost:5432/docpilot_test"
    )

    environment = migration_health.migration_environment(database_url)

    assert environment["DOCPILOT_DATABASE_URL"] == (
        "postgresql+psycopg://user:fixture-password@localhost:5432/docpilot_test"
    )
    assert environment["DOCPILOT_TEST_DATABASE_URL"] == environment["DOCPILOT_DATABASE_URL"]
    assert "***" not in environment["DOCPILOT_DATABASE_URL"]


def test_drop_scratch_database_rejects_non_scratch_name() -> None:
    with pytest.raises(migration_health.UnsafeTestDatabaseError):
        migration_health.drop_scratch_database(
            migration_health.normalize_postgres_driver("postgresql://user:secret@localhost:5432/docpilot_test")
        )
