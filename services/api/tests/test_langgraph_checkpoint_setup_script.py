"""Unit tests for the one-time LangGraph checkpoint setup entry point."""

import importlib.util
from pathlib import Path

import pytest


_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "setup_langgraph_checkpoints.py"
_SPEC = importlib.util.spec_from_file_location("setup_langgraph_checkpoints", _SCRIPT_PATH)
assert _SPEC is not None
checkpoint_setup = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(checkpoint_setup)


def test_checkpoint_connection_url_removes_sqlalchemy_driver_name() -> None:
    url = "postgresql+psycopg://user:password@db.internal:5432/bidpilot"

    assert checkpoint_setup.checkpoint_connection_url(url) == "postgresql://user:password@db.internal:5432/bidpilot"


def test_checkpoint_connection_url_requires_a_value() -> None:
    with pytest.raises(RuntimeError, match="DOCPILOT_DATABASE_URL"):
        checkpoint_setup.checkpoint_connection_url("   ")
