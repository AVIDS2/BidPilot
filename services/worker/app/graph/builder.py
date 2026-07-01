"""BidPilot LangGraph graph builder.

Assembles the full agent graph with all nodes and conditional edges.
The compiled graph is exposed via lazy-initialization helpers so that
module import does **not** require a live PostgreSQL connection::

    from app.graph.builder import get_graph
    result = get_graph().invoke(initial_state)

For backward compatibility, ``graph`` is still importable but delegates
to ``get_graph()`` behind the scenes.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import atexit
from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import InMemorySaver

from .state import BidPilotState
from .nodes.supervisor import (
    supervisor_node,
    route_initial,
    route_after_rfp,
    route_after_retrieval,
    route_after_draft,
    route_after_review,
    route_after_human_approval,
)
from .nodes.rfp_parser import rfp_parser_node
from .nodes.knowledge_retriever import knowledge_retriever_node
from .nodes.section_drafter import section_drafter_node
from .nodes.quality_reviewer import quality_reviewer_node
from .nodes.human_approval import human_approval_node
from .nodes.persist_result import persist_result_node

logger = logging.getLogger(__name__)

# ── Thread-safe lazy initialization ───────────────────────────────────

_checkpointer: Any | None = None
_checkpointer_cm = None
_graph = None  # CompiledGraph | None
_init_lock = threading.RLock()


def _build_graph() -> StateGraph:
    """Construct and return the uncompiled BidPilot agent graph.

    Graph topology::

        __start__ -> supervisor
        supervisor -> rfp_parser        (if requirements not parsed)
        supervisor -> knowledge_retriever (if evidence not retrieved)
        supervisor -> section_drafter    (if draft not created)
        supervisor -> quality_reviewer   (if draft exists, no review)
        supervisor -> human_approval     (if review passed, HITL pause)
        supervisor -> persist_result     (if human approved or max iterations)

        rfp_parser -> knowledge_retriever
        knowledge_retriever -> section_drafter
        section_drafter -> quality_reviewer

        quality_reviewer -> human_approval   (review passed)
        quality_reviewer -> section_drafter  (review failed, iteration < max)
        quality_reviewer -> persist_result   (review failed, iteration >= max)

        human_approval -> persist_result     (human approved)
        human_approval -> section_drafter    (human rejected with feedback)

        persist_result -> __end__
    """
    sg = StateGraph(BidPilotState)

    # ── Register nodes ────────────────────────────────────────────────
    sg.add_node("supervisor", supervisor_node)
    sg.add_node("rfp_parser", rfp_parser_node)
    sg.add_node("knowledge_retriever", knowledge_retriever_node)
    sg.add_node("section_drafter", section_drafter_node)
    sg.add_node("quality_reviewer", quality_reviewer_node)
    sg.add_node("human_approval", human_approval_node)
    sg.add_node("persist_result", persist_result_node)

    # ── Entry point ───────────────────────────────────────────────────
    sg.set_entry_point("supervisor")

    # ── Conditional edges from supervisor ─────────────────────────────
    sg.add_conditional_edges(
        "supervisor",
        route_initial,
        {
            "rfp_parser": "rfp_parser",
            "knowledge_retriever": "knowledge_retriever",
            "section_drafter": "section_drafter",
            "quality_reviewer": "quality_reviewer",
            "human_approval": "human_approval",
            "persist_result": "persist_result",
        },
    )

    # ── Linear edges ──────────────────────────────────────────────────
    sg.add_conditional_edges("rfp_parser", route_after_rfp, {"knowledge_retriever": "knowledge_retriever"})
    sg.add_conditional_edges("knowledge_retriever", route_after_retrieval, {"section_drafter": "section_drafter"})
    sg.add_conditional_edges("section_drafter", route_after_draft, {"quality_reviewer": "quality_reviewer"})

    # ── Conditional edges from quality reviewer ───────────────────────
    sg.add_conditional_edges(
        "quality_reviewer",
        route_after_review,
        {
            "human_approval": "human_approval",
            "persist_result": "persist_result",
            "section_drafter": "section_drafter",
        },
    )

    # ── Conditional edges from human approval (HITL) ─────────────────
    sg.add_conditional_edges(
        "human_approval",
        route_after_human_approval,
        {
            "persist_result": "persist_result",
            "section_drafter": "section_drafter",
        },
    )

    # ── Terminal edge ─────────────────────────────────────────────────
    sg.add_edge("persist_result", END)

    return sg


def _create_checkpointer() -> Any:
    """Create a PostgresSaver checkpointer connected to the application DB.

    Uses the same DATABASE_URL as the rest of the worker.  Calls ``setup()``
    on first use to create the checkpoint tables if they don't exist.

    Raises:
        RuntimeError: If the database connection or table setup fails.
    """
    checkpointer_mode = os.environ.get("DOCPILOT_LANGGRAPH_CHECKPOINTER", "postgres").lower()
    if checkpointer_mode == "memory":
        logger.warning(
            "Using in-memory LangGraph checkpointer. This is for local smoke tests only."
        )
        return InMemorySaver()

    database_url = os.environ.get(
        "DOCPILOT_DATABASE_URL",
        "postgresql+psycopg://docpilot:docpilot@localhost:5433/docpilot",
    )
    # PostgresSaver uses psycopg directly, not SQLAlchemy URL dialects.
    checkpointer_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    try:
        global _checkpointer_cm
        checkpointer_cm = PostgresSaver.from_conn_string(checkpointer_url)
        checkpointer = checkpointer_cm.__enter__()
        # Ensure checkpoint tables exist
        checkpointer.setup()
        _checkpointer_cm = checkpointer_cm
        return checkpointer
    except Exception as exc:
        if "checkpointer_cm" in locals():
            checkpointer_cm.__exit__(*sys.exc_info())
        raise RuntimeError(
            f"Failed to initialize PostgresSaver checkpointer "
            f"(URL: {database_url.split('@')[-1] if '@' in database_url else database_url}): {exc}"
        ) from exc


def close_checkpointer() -> None:
    """Close the module-level PostgresSaver context if it was opened."""
    global _checkpointer, _checkpointer_cm, _graph
    if _checkpointer_cm is not None:
        _checkpointer_cm.__exit__(None, None, None)
    _checkpointer = None
    _checkpointer_cm = None
    _graph = None


atexit.register(close_checkpointer)


def get_checkpointer() -> Any:
    """Return the module-level PostgresSaver, creating it on first call.

    Thread-safe: uses a lock so that concurrent callers from multiple
    worker threads do not create duplicate connections.
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    with _init_lock:
        # Double-check after acquiring the lock
        if _checkpointer is not None:
            return _checkpointer
        logger.info("Initializing PostgresSaver checkpointer (lazy init) ...")
        _checkpointer = _create_checkpointer()
        logger.info("PostgresSaver checkpointer ready.")
        return _checkpointer


def get_graph():
    """Return the compiled BidPilot graph, creating it on first call.

    Thread-safe: uses a lock so that concurrent callers from multiple
    worker threads do not create duplicate compiled graphs.

    Returns:
        The compiled LangGraph graph with checkpointer attached.
    """
    global _graph
    if _graph is not None:
        return _graph

    with _init_lock:
        # Double-check after acquiring the lock
        if _graph is not None:
            return _graph
        logger.info("Building and compiling BidPilot graph (lazy init) ...")
        checkpointer = get_checkpointer()
        _graph = _build_graph().compile(
            checkpointer=checkpointer,
            interrupt_before=["human_approval"],
        )
        logger.info("BidPilot graph compiled and ready.")
        return _graph


class _LazyGraph:
    """Proxy that delegates every attribute access to ``get_graph()``.

    Allows existing code to keep using ``from app.graph.builder import graph``
    without hitting PostgreSQL at import time.
    """

    def __getattr__(self, name: str):
        return getattr(get_graph(), name)

    def __repr__(self) -> str:
        return f"<LazyGraph wrapping {get_graph()!r}>"


# Backward-compatible module-level name.
graph = _LazyGraph()


# ── Convenience functions ─────────────────────────────────────────────

def invoke_graph(
    project_id: str,
    section_key: str,
    run_id: str,
    provider_config_id: str | None = None,
    reasoning_effort: str | None = None,
    review_feedback: str | None = None,
    input_review_feedback: str | None = None,
    max_iterations: int = 3,
    thread_id: str | None = None,
) -> dict:
    """Convenience function to invoke the compiled graph with minimal inputs.

    Constructs the initial state dict, invokes the graph, and returns the
    final state.

    Args:
        project_id: UUID of the project.
        section_key: Kebab-case section identifier (e.g. "exec-summary").
        run_id: UUID of the ExecutionRun record.
        provider_config_id: Optional user provider config UUID.
        reasoning_effort: Optional reasoning intensity for supported models.
        review_feedback: (deprecated) Use input_review_feedback instead.
            If both are provided, input_review_feedback takes precedence.
        input_review_feedback: Optional review feedback for revision rounds.
        max_iterations: Maximum drafting iterations before giving up.
        thread_id: Optional checkpoint thread ID. Defaults to run_id.

    Returns:
        The final BidPilotState dict after graph execution completes.
    """
    # Backward compatibility: accept old param name
    effective_feedback = input_review_feedback or review_feedback

    initial_state: BidPilotState = {
        "project_id": project_id,
        "section_key": section_key,
        "run_id": run_id,
        "provider_config_id": provider_config_id,
        "reasoning_effort": reasoning_effort,
        "input_review_feedback": effective_feedback,
        "requirements": [],
        "requirements_parsed": False,
        "evidence_chunks": [],
        "evidence_retrieved": False,
        "draft_markdown": "",
        "draft_model_used": "",
        "draft_created": False,
        "review_result": None,  # type: ignore[typeddict-item]
        "review_passed": False,
        "section_version_id": None,
        "persisted": False,
        "human_decision": None,
        "human_feedback": None,
        "iteration": 0,
        "max_iterations": max_iterations,
        "error": None,
        "agent_history": [],
        "context_summary": None,
    }

    config = {"configurable": {"thread_id": thread_id or run_id}}

    logger.info(
        "Invoking BidPilot graph: project=%s section=%s run=%s max_iter=%d",
        project_id,
        section_key,
        run_id,
        max_iterations,
    )

    result = get_graph().invoke(initial_state, config=config)

    logger.info(
        "Graph completed: section=%s persisted=%s iteration=%d error=%s",
        section_key,
        result.get("persisted"),
        result.get("iteration"),
        result.get("error"),
    )

    return result


def resume_graph(
    run_id: str,
    decision: str,
    feedback: str | None = None,
    thread_id: str | None = None,
) -> dict:
    """Resume an interrupted LangGraph graph after human approval.

    The graph pauses at the ``human_approval`` node via ``interrupt_before``.
    This function sends a ``Command(resume=...)`` to continue execution.

    Args:
        run_id: UUID of the ExecutionRun (also used as default thread_id).
        decision: "approved" or "rejected_with_feedback".
        feedback: Optional reviewer feedback when decision is "rejected_with_feedback".
        thread_id: Optional checkpoint thread ID. Defaults to run_id.

    Returns:
        The final BidPilotState dict after graph execution completes.
    """
    from langgraph.types import Command

    config = {"configurable": {"thread_id": thread_id or run_id}}

    resume_payload = {
        "decision": decision,
        "feedback": feedback,
    }

    logger.info(
        "Resuming BidPilot graph: run=%s decision=%s",
        run_id,
        decision,
    )

    result = get_graph().invoke(Command(resume=resume_payload), config=config)

    logger.info(
        "Graph resumed and completed: run=%s persisted=%s decision=%s",
        run_id,
        result.get("persisted"),
        decision,
    )

    return result
