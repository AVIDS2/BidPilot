"""Production safety checks for the interactive LangGraph checkpointer."""

import pytest
from langgraph.checkpoint.memory import InMemorySaver

import app.agent.graph as agent_graph


@pytest.fixture(autouse=True)
def _reset_checkpointer() -> None:
    agent_graph.close_checkpointer()
    yield
    agent_graph.close_checkpointer()


def test_agent_checkpointer_rejects_memory_mode_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCPILOT_ENV", "production")
    monkeypatch.setenv("DOCPILOT_AGENT_CHECKPOINTER", "memory")

    with pytest.raises(RuntimeError, match="must be postgres"):
        agent_graph.get_checkpointer()


def test_agent_checkpointer_allows_explicit_memory_mode_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCPILOT_ENV", "local")
    monkeypatch.setenv("DOCPILOT_AGENT_CHECKPOINTER", "memory")

    assert isinstance(agent_graph.get_checkpointer(), InMemorySaver)
