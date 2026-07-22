"""Production safety checks for the workflow LangGraph checkpointer."""

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.graph import builder


@pytest.fixture(autouse=True)
def _reset_checkpointer() -> None:
    builder.close_checkpointer()
    yield
    builder.close_checkpointer()


def test_workflow_checkpointer_rejects_memory_mode_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCPILOT_ENV", "production")
    monkeypatch.setenv("DOCPILOT_LANGGRAPH_CHECKPOINTER", "memory")

    with pytest.raises(RuntimeError, match="must be postgres"):
        builder.get_checkpointer()


def test_workflow_checkpointer_allows_explicit_memory_mode_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCPILOT_ENV", "local")
    monkeypatch.setenv("DOCPILOT_LANGGRAPH_CHECKPOINTER", "memory")

    assert isinstance(builder.get_checkpointer(), InMemorySaver)
