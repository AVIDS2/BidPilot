from scripts.test_database_safety import (
    UnsafeTestDatabaseError,
    build_test_environment,
    database_name,
    resolve_test_database_url,
)
from scripts.prepare_local_test_database import normalize_postgres_driver


def test_database_name_ignores_credentials_and_query() -> None:
    assert (
        database_name("postgresql+psycopg://user:secret@localhost:5432/docpilot_test?sslmode=disable")
        == "docpilot_test"
    )


def test_prepare_test_database_uses_installed_psycopg_driver_for_plain_url() -> None:
    url = normalize_postgres_driver("postgresql://test:secret@localhost/docpilot_test")

    assert url.drivername == "postgresql+psycopg"
    assert url.database == "docpilot_test"


def test_explicit_test_database_url_overrides_application_url() -> None:
    environment = {
        "DOCPILOT_DATABASE_URL": "postgresql://app:secret@localhost/docpilot",
        "DOCPILOT_TEST_DATABASE_URL": "postgresql://test:secret@localhost/docpilot_test",
    }

    result = build_test_environment(environment)

    assert result["DOCPILOT_DATABASE_URL"] == environment["DOCPILOT_TEST_DATABASE_URL"]
    assert result["DOCPILOT_TEST_DATABASE_URL"] == environment["DOCPILOT_TEST_DATABASE_URL"]


def test_non_test_database_is_rejected() -> None:
    try:
        resolve_test_database_url(
            {"DOCPILOT_DATABASE_URL": "postgresql://app:secret@localhost/docpilot"}
        )
    except UnsafeTestDatabaseError:
        return
    raise AssertionError("expected an unsafe database URL to be rejected")
