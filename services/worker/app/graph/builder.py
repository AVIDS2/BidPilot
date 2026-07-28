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
import threading
import atexit
from functools import wraps
from typing import Any

from langgraph.errors import GraphInterrupt
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import InMemorySaver

from .state import BidPilotState
from .nodes.supervisor import (
    supervisor_node,
    route_initial,
    route_after_rfp,
    route_after_retrieval,
    route_after_content_plan,
    route_after_draft,
    route_after_review,
    route_after_persist,
    route_after_human_approval,
)
from .nodes.rfp_parser import rfp_parser_node
from .nodes.memory_context import load_memory_context_node
from .nodes.memory_proposals import propose_memory_updates_node
from .nodes.knowledge_retriever import knowledge_retriever_node
from .nodes.content_plan import content_plan_node
from .nodes.section_drafter import section_drafter_node
from .nodes.quality_reviewer import quality_reviewer_node
from .nodes.human_approval import human_approval_node
from .nodes.persist_result import persist_result_node
from app.runtime.events import (
    RuntimeCancellationRequested,
    is_runtime_cancellation_requested,
    publish_cancellation_detected,
    publish_node_failed,
    publish_node_started,
    publish_node_succeeded,
)

logger = logging.getLogger(__name__)

# ── Thread-safe lazy initialization ───────────────────────────────────

_checkpointer: Any | None = None
_checkpointer_cm = None
_graph = None  # CompiledGraph | None
_init_lock = threading.RLock()


def _is_production_environment() -> bool:
    return os.environ.get("DOCPILOT_ENV", "local").lower() in {"production", "staging"}


def _instrument_node(node_name: str, node):
    """Publish product runtime progress around a graph node invocation."""

    @wraps(node)
    def wrapped(state: BidPilotState) -> dict:
        runtime_run_id = state.get("runtime_run_id")
        if is_runtime_cancellation_requested(runtime_run_id):
            publish_cancellation_detected(runtime_run_id, node_name)
            raise RuntimeCancellationRequested()
        publish_node_started(runtime_run_id, node_name)
        try:
            result = node(state)
        except RuntimeCancellationRequested:
            raise
        except GraphInterrupt:
            # Human approval publishes its own durable pause event before it interrupts.
            raise
        except Exception:
            publish_node_failed(
                runtime_run_id,
                node_name,
                "Unexpected graph node failure",
                error_code="workflow_node_exception",
            )
            raise
        # A cancellation can arrive while a node is running. The node is
        # allowed to reach its own transactional boundary, but the graph must
        # not start another node or report a completed workflow afterwards.
        if is_runtime_cancellation_requested(runtime_run_id):
            publish_cancellation_detected(runtime_run_id, node_name)
            raise RuntimeCancellationRequested()
        if result.get("error"):
            publish_node_failed(
                runtime_run_id,
                node_name,
                str(result["error"]),
                error_code=str(result.get("provider_error_code") or "workflow_node_failed"),
            )
        else:
            publish_node_succeeded(
                runtime_run_id,
                node_name,
                _node_summary(node_name, result),
                _node_payload(node_name, result),
            )
        return result

    return wrapped


def _node_summary(node_name: str, result: dict) -> str:
    if node_name == "rfp_parser":
        return f"已识别 {len(result.get('requirements', []))} 条招标需求。"
    if node_name == "knowledge_retriever":
        return f"已检索到 {len(result.get('evidence_chunks', []))} 条相关证据。"
    if node_name == "content_plan":
        plan = result.get("content_plan") or {}
        return (
            f"内容计划已生成：{len(plan.get('key_points') or [])} 个要点，"
            f"{len(plan.get('tables') or [])} 个表格建议。"
        )
    if node_name == "memory_context":
        return f"已加载 {len(result.get('memory_context_items', []))} 条授权记忆。"
    if node_name == "section_drafter":
        return "章节草稿已生成。" if result.get("draft_created") else "章节草稿未能生成。"
    if node_name == "quality_reviewer":
        review = result.get("review_result") or {}
        return "质量审核已通过。" if review.get("passed") else "质量审核发现待处理问题。"
    if node_name == "human_approval":
        return "人工审核意见已收到。"
    if node_name == "persist_result":
        return "草稿和证据已保存。" if result.get("persisted") else "结果保存未完成。"
    if node_name == "memory_proposals":
        return f"已生成 {len(result.get('memory_proposal_ids', []))} 条待审核知识提案。"
    return "工作流步骤已完成。"


def _node_payload(node_name: str, result: dict) -> dict:
    if node_name == "rfp_parser":
        return {"requirement_count": len(result.get("requirements", []))}
    if node_name == "knowledge_retriever":
        payload = {"evidence_count": len(result.get("evidence_chunks", []))}
        for key in (
            "retrieval_candidate_count",
            "retrieval_fused_candidate_count",
            "retrieval_reranked_candidate_count",
            "retrieval_latency_ms",
        ):
            value = result.get(key)
            if type(value) is int and value >= 0:
                payload[key] = value
        return payload
    if node_name == "content_plan":
        plan = result.get("content_plan") or {}
        return {
            "response_plan_id": result.get("response_plan_id"),
            "response_plan_version": result.get("response_plan_version"),
            "key_point_count": len(plan.get("key_points") or []),
            "table_count": len(plan.get("tables") or []),
            "figure_count": len(plan.get("figures") or []),
            "gap_count": len(plan.get("gaps") or []),
        }
    if node_name == "memory_context":
        return {
            "memory_count": len(result.get("memory_context_items", [])),
            "degraded_reasons": result.get("memory_context_degraded_reasons", []),
        }
    if node_name == "quality_reviewer":
        review = result.get("review_result") or {}
        return {
            "passed": bool(review.get("passed")),
            "score": review.get("overall_score"),
            "claim_candidate_count": len(result.get("claim_candidates", [])),
            "claim_integrity_status": result.get("claim_integrity_status"),
        }
    if node_name == "persist_result":
        return {
            "section_version_id": result.get("section_version_id"),
            "claim_count": result.get("claim_count", 0),
            "claim_integrity_status": result.get("claim_integrity_status"),
        }
    if node_name == "memory_proposals":
        return {"proposal_count": len(result.get("memory_proposal_ids", []))}
    return {}


def _build_graph() -> StateGraph:
    """Construct and return the uncompiled BidPilot agent graph.

    Graph topology::

        __start__ -> supervisor
        supervisor -> rfp_parser        (if requirements not parsed)
        supervisor -> knowledge_retriever (if evidence not retrieved)
        supervisor -> content_plan       (if evidence ready, plan missing)
        supervisor -> section_drafter    (if plan ready, draft missing)
        supervisor -> quality_reviewer   (if draft exists, no review)
        supervisor -> persist_result     (if review passed, approval resolved, or max iterations)

        rfp_parser -> knowledge_retriever
        knowledge_retriever -> content_plan
        content_plan -> section_drafter
        section_drafter -> quality_reviewer

        quality_reviewer -> persist_result   (review passed; writes immutable review candidate)
        quality_reviewer -> content_plan     (review failed, iteration < max)
        quality_reviewer -> persist_result   (review failed, iteration >= max)

        human_approval -> persist_result     (human approved)
        human_approval -> content_plan       (human rejected with feedback)

        persist_result -> human_approval     (new reviewed candidate)
        persist_result -> memory_proposals   (terminal persistence)
    """
    sg = StateGraph(BidPilotState)

    # ── Register nodes ────────────────────────────────────────────────
    sg.add_node("supervisor", _instrument_node("supervisor", supervisor_node))
    sg.add_node("rfp_parser", _instrument_node("rfp_parser", rfp_parser_node))
    sg.add_node("memory_context", _instrument_node("memory_context", load_memory_context_node))
    sg.add_node("knowledge_retriever", _instrument_node("knowledge_retriever", knowledge_retriever_node))
    sg.add_node("content_plan", _instrument_node("content_plan", content_plan_node))
    sg.add_node("section_drafter", _instrument_node("section_drafter", section_drafter_node))
    sg.add_node("quality_reviewer", _instrument_node("quality_reviewer", quality_reviewer_node))
    sg.add_node("human_approval", _instrument_node("human_approval", human_approval_node))
    sg.add_node("persist_result", _instrument_node("persist_result", persist_result_node))
    sg.add_node("memory_proposals", _instrument_node("memory_proposals", propose_memory_updates_node))

    # ── Entry point ───────────────────────────────────────────────────
    sg.set_entry_point("supervisor")

    # ── Conditional edges from supervisor ─────────────────────────────
    sg.add_conditional_edges(
        "supervisor",
        route_initial,
        {
            "rfp_parser": "rfp_parser",
            "memory_context": "memory_context",
            "knowledge_retriever": "knowledge_retriever",
            "content_plan": "content_plan",
            "section_drafter": "section_drafter",
            "quality_reviewer": "quality_reviewer",
            "human_approval": "human_approval",
            "persist_result": "persist_result",
        },
    )

    # ── Linear edges ──────────────────────────────────────────────────
    sg.add_conditional_edges("rfp_parser", route_after_rfp, {"memory_context": "memory_context"})
    sg.add_edge("memory_context", "knowledge_retriever")
    sg.add_conditional_edges(
        "knowledge_retriever",
        route_after_retrieval,
        {"content_plan": "content_plan", "failed": END},
    )
    sg.add_conditional_edges(
        "content_plan",
        route_after_content_plan,
        {"section_drafter": "section_drafter", "failed": END},
    )
    sg.add_conditional_edges(
        "section_drafter",
        route_after_draft,
        {"quality_reviewer": "quality_reviewer", "failed": END},
    )

    # ── Conditional edges from quality reviewer ───────────────────────
    sg.add_conditional_edges(
        "quality_reviewer",
        route_after_review,
        {
            "persist_result": "persist_result",
            "content_plan": "content_plan",
            "failed": END,
        },
    )

    # ── Conditional edges from human approval (HITL) ─────────────────
    sg.add_conditional_edges(
        "human_approval",
        route_after_human_approval,
        {
            "persist_result": "persist_result",
            "content_plan": "content_plan",
        },
    )

    # ── Persistence either opens a durable human-review checkpoint or
    # reaches terminal memory proposal generation.
    sg.add_conditional_edges(
        "persist_result",
        route_after_persist,
        {
            "human_approval": "human_approval",
            "memory_proposals": "memory_proposals",
        },
    )
    sg.add_edge("memory_proposals", END)

    return sg


def _create_checkpointer() -> Any:
    """Create a PostgresSaver checkpointer connected to the application DB.

    Uses the same DATABASE_URL as the rest of the worker. Checkpoint tables
    are initialized by the deployment setup script before the worker starts.

    Raises:
        RuntimeError: If the database connection cannot be opened.
    """
    checkpointer_mode = os.environ.get("DOCPILOT_LANGGRAPH_CHECKPOINTER", "postgres").lower()
    if checkpointer_mode == "memory":
        if _is_production_environment():
            raise RuntimeError("DOCPILOT_LANGGRAPH_CHECKPOINTER must be postgres outside local development")
        logger.warning(
            "Using explicit local in-memory LangGraph checkpointer. This is for smoke tests only."
        )
        return InMemorySaver()
    if checkpointer_mode != "postgres":
        raise RuntimeError(f"Unsupported DOCPILOT_LANGGRAPH_CHECKPOINTER mode: {checkpointer_mode}")

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
        _checkpointer_cm = checkpointer_cm
        return checkpointer
    except Exception as exc:
        if "checkpointer_cm" in locals():
            checkpointer_cm.__exit__(None, None, None)
        raise RuntimeError(
            "PostgreSQL workflow checkpointer initialization failed. "
            "Run scripts/setup_langgraph_checkpoints.py during deployment before starting API or Worker."
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
        _graph = _build_graph().compile(checkpointer=checkpointer)
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
    runtime_run_id: str | None = None,
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
        "runtime_run_id": runtime_run_id,
        "provider_config_id": provider_config_id,
        "reasoning_effort": reasoning_effort,
        "input_review_feedback": effective_feedback,
        "requirements": [],
        "requirements_parsed": False,
        "memory_context_loaded": False,
        "memory_context_items": [],
        "memory_context_version": None,
        "memory_context_degraded_reasons": [],
        "memory_proposal_ids": [],
        "evidence_set_id": None,
        "evidence_set_status": None,
        "evidence_set_unmet_requirement_ids": [],
        "evidence_set_degraded_reasons": [],
        "evidence_chunks": [],
        "evidence_retrieved": False,
        "content_plan": None,
        "content_plan_ready": False,
        "response_plan_id": None,
        "response_plan_section_id": None,
        "response_plan_evidence_binding_id": None,
        "response_plan_version": None,
        "draft_markdown": "",
        "draft_model_used": "",
        "draft_created": False,
        "provider_error_code": None,
        "review_result": None,  # type: ignore[typeddict-item]
        "review_passed": False,
        "claim_candidates": [],
        "claim_integrity_status": "not_assessed",
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

    The graph pauses inside ``human_approval_node`` via dynamic ``interrupt()``
    (LangGraph's recommended HITL pattern, not static interrupt_before).
    This function sends a ``Command(resume=...)`` to continue execution.

    Args:
        run_id: UUID of the ExecutionRun (also used as default thread_id).
        decision: "approved" or "rejected_with_feedback".
        feedback: Optional reviewer feedback when decision is "rejected_with_feedback".
        thread_id: Optional checkpoint thread ID. Defaults to run_id.

    Returns:
        The final BidPilotState dict after graph execution completes.
    """
    if decision not in {"approved", "rejected_with_feedback"}:
        raise ValueError("Unsupported LangGraph human approval decision")
    if feedback is not None and not isinstance(feedback, str):
        raise ValueError("LangGraph human approval feedback must be a string")

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
