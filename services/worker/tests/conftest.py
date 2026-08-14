import os
import sys
from pathlib import Path

import pytest

# Ensure the app package is importable from the services/worker root
worker_root = Path(__file__).resolve().parent.parent
if str(worker_root) not in sys.path:
    sys.path.insert(0, str(worker_root))

# Ensure shared packages are importable
repo_root = worker_root.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from scripts.test_database_safety import UnsafeTestDatabaseError, resolve_test_database_url  # noqa: E402


try:
    _test_database_url = resolve_test_database_url(os.environ)
except UnsafeTestDatabaseError as exc:
    pytest.exit(str(exc), returncode=2)

os.environ["DOCPILOT_DATABASE_URL"] = _test_database_url
os.environ["DOCPILOT_TEST_DATABASE_URL"] = _test_database_url
if _test_database_url.startswith("sqlite:///"):
    # SQLite is only the local unit-test adapter. Graph compilation still
    # exercises the same nodes, but durable checkpoint integration belongs to
    # the PostgreSQL test/staging lane.
    os.environ["DOCPILOT_LANGGRAPH_CHECKPOINTER"] = "memory"
    os.environ["DOCPILOT_ENV"] = "test"


def pytest_sessionstart(session: pytest.Session) -> None:
    """Prepare Worker test persistence before graph task tests run.

    Production creates these tables in an ordered one-shot deployment service;
    tests use the same checkpoint setup code against the dedicated ``*_test``
    database. SQLite is intentionally only a fast unit-test adapter, so create
    the shared SQLAlchemy schema there instead of requiring a manually seeded
    local file.
    """
    del session
    if _test_database_url.startswith("sqlite:///"):
        import app.models  # noqa: F401

        from app.db import engine
        from contracts.db import Base

        Base.metadata.create_all(bind=engine)
    if os.environ.get("DOCPILOT_LANGGRAPH_CHECKPOINTER", "postgres").lower() != "postgres":
        return
    if not _test_database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        return

    from langgraph.checkpoint.postgres import PostgresSaver

    from scripts.setup_langgraph_checkpoints import checkpoint_connection_url

    with PostgresSaver.from_conn_string(checkpoint_connection_url(_test_database_url)) as checkpointer:
        checkpointer.setup()


@pytest.fixture(autouse=True)
def isolate_provider_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent Worker tests from inheriting billable chat credentials."""
    for name in (
        "LLM_API_KEY",
        "LLM_API_URL",
        "LLM_MODEL",
        "OPENCODE_API_KEY",
        "OPENCODE_BASE_URL",
        "OPENCODE_MODEL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "DOCPILOT_PROVIDER_DOMESTIC_API_KEY",
        "DOCPILOT_PROVIDER_DOMESTIC_BASE_URL",
        "DOCPILOT_LLM_MODEL_PRIMARY",
        "ALIYUN_API_KEY",
        "DASHSCOPE_API_KEY",
        "DOCPILOT_PROVIDER_OPENAI_API_KEY",
        "DOCPILOT_PROVIDER_OPENAI_BASE_URL",
        "OPENAI_API_KEY",
        "DOCPILOT_PROVIDER_ANTHROPIC_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DOCPILOT_ALLOW_STUB_LLM", "true")
