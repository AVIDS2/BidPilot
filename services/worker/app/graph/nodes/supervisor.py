"""Deterministic routing for the BidPilot LangGraph workflow."""

from __future__ import annotations

import logging
import time

from ..state import BidPilotState
from ._history import record_agent_call

logger = logging.getLogger(__name__)


def _deterministic_routing(state: BidPilotState) -> str:
    """Choose the next graph node from durable workflow state only."""
    if not state.get("requirements_parsed"):
        return "rfp_parser"
    if not state.get("memory_context_loaded"):
        return "memory_context"
    if not state.get("evidence_retrieved"):
        return "knowledge_retriever"
    if not state.get("content_plan_ready"):
        return "content_plan"
    if not state.get("draft_created"):
        return "section_drafter"
    if not state.get("review_passed") and state.get("review_result") is None:
        return "quality_reviewer"
    if state.get("review_passed") and state.get("human_decision") is None:
        return "human_approval"
    if state.get("human_decision") == "rejected_with_feedback":
        # Re-plan on human rejection so feedback can reshape the outline.
        return "content_plan"
    return "persist_result"


def supervisor_node(state: BidPilotState) -> dict:
    """Record a deterministic routing decision without spending model budget."""
    start = time.monotonic()
    current_iteration = state.get("iteration", 0)
    target = _deterministic_routing(state)
    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "Supervisor routing (iteration %d/%d): target=%s",
        current_iteration,
        state.get("max_iterations", 3),
        target,
    )
    history = record_agent_call(
        agent="supervisor",
        action="route_decision",
        input_summary=(
            f"iteration={current_iteration}/{state.get('max_iterations', 3)}, "
            f"parsed={state.get('requirements_parsed')}, "
            f"retrieved={state.get('evidence_retrieved')}, "
            f"draft={state.get('draft_created')}, "
            f"review_passed={state.get('review_passed')}, "
            f"human_decision={state.get('human_decision')}"
        ),
        output_summary=f"iteration={current_iteration}, routing=deterministic, target={target}",
        duration_ms=duration_ms,
        success=True,
    )
    return {"iteration": current_iteration, "agent_history": history}


def route_after_review(state: BidPilotState) -> str:
    """Route to approval, redraft, or persistence after quality review."""
    review_passed: bool = state.get("review_passed", False)
    iteration: int = state.get("iteration", 0)
    max_iterations: int = state.get("max_iterations", 3)
    if review_passed:
        logger.info("Review passed on iteration %d — routing to human approval", iteration)
        return "human_approval"
    if iteration < max_iterations:
        logger.info(
            "Review failed on iteration %d/%d — re-planning then redrafting",
            iteration,
            max_iterations,
        )
        return "content_plan"
    logger.warning("Review failed after %d iterations - persisting draft as-is", iteration)
    return "persist_result"


def route_after_human_approval(state: BidPilotState) -> str:
    """Route human approval results without relying on inferred intent."""
    decision: str = state.get("human_decision", "approved")
    section_key: str = state.get("section_key", "")
    if decision == "approved":
        logger.info("Human approved draft for %s — persisting", section_key)
        return "persist_result"
    if decision == "rejected_with_feedback":
        feedback = state.get("human_feedback", "")
        logger.info(
            "Human rejected draft for %s — re-planning with feedback (%d chars)",
            section_key,
            len(feedback) if feedback else 0,
        )
        return "content_plan"
    logger.warning("Unexpected human decision for %s — persisting as-is", section_key)
    return "persist_result"


def route_initial(state: BidPilotState) -> str:
    """Choose the first node from the same deterministic rule set."""
    return _deterministic_routing(state)


def route_after_rfp(state: BidPilotState) -> str:
    """Load authorized memory after requirements are available."""
    return "memory_context"


def route_after_retrieval(state: BidPilotState) -> str:
    """Plan content structure after retrieval completes."""
    return "content_plan"


def route_after_content_plan(state: BidPilotState) -> str:
    """Draft after the content plan is ready."""
    return "section_drafter"


def route_after_draft(state: BidPilotState) -> str:
    """Stop a failed provider draft before it can persist an empty version."""
    if state.get("error"):
        return "failed"
    return "quality_reviewer"
