"""Safe, dependency-light test database selection for local and CI commands."""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlsplit


class UnsafeTestDatabaseError(ValueError):
    """Raised before tests can accidentally mutate a non-test database."""


def database_name(database_url: str) -> str:
    """Extract the database path component without ever exposing credentials."""
    parsed = urlsplit(database_url)
    name = parsed.path.rstrip("/").rsplit("/", maxsplit=1)[-1]
    return name.strip()


def is_test_database_url(database_url: str) -> bool:
    return database_name(database_url).lower().endswith("_test")


def resolve_test_database_url(environment: Mapping[str, str]) -> str:
    """Return the only database URL a test process may use.

    An explicit test URL wins. Otherwise a normal application URL is accepted
    only when the database name already identifies it as a dedicated test DB.
    """
    database_url = environment.get("DOCPILOT_TEST_DATABASE_URL") or environment.get(
        "DOCPILOT_DATABASE_URL",
        "",
    )
    if not database_url:
        raise UnsafeTestDatabaseError(
            "Set DOCPILOT_TEST_DATABASE_URL to a dedicated database ending in _test before running tests"
        )
    if not is_test_database_url(database_url):
        raise UnsafeTestDatabaseError(
            "Refusing to run tests against a database not ending in _test; set DOCPILOT_TEST_DATABASE_URL"
        )
    return database_url


def build_test_environment(environment: Mapping[str, str]) -> dict[str, str]:
    """Return a child-process environment pinned to the dedicated test DB."""
    test_database_url = resolve_test_database_url(environment)
    result = dict(environment)
    result["DOCPILOT_DATABASE_URL"] = test_database_url
    result["DOCPILOT_TEST_DATABASE_URL"] = test_database_url
    return result
