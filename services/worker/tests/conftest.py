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


@pytest.fixture(autouse=True)
def isolate_provider_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent Worker tests from inheriting billable chat credentials."""
    for name in (
        "LLM_API_KEY",
        "DOCPILOT_PROVIDER_DOMESTIC_API_KEY",
        "ALIYUN_API_KEY",
        "DASHSCOPE_API_KEY",
        "DOCPILOT_PROVIDER_OPENAI_API_KEY",
        "OPENAI_API_KEY",
        "DOCPILOT_PROVIDER_ANTHROPIC_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DOCPILOT_ALLOW_STUB_LLM", "true")
