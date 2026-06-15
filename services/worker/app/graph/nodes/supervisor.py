"""Supervisor node: LLM-enhanced routing for the BidPilot graph.

Primary: Uses ChatOpenAI (gpt-4o-mini) for intelligent routing decisions.
Fallback: Deterministic state-inspection routing when LLM is unavailable.

The routing logic checks state flags to determine which node runs next:

1. No requirements parsed          -> "rfp_parser"
2. No evidence retrieved           -> "knowledge_retriever"
3. No draft created                -> "section_drafter"
4. Draft exists, no review yet     -> "quality_reviewer"
5. Review passed, no human yet     -> "human_approval"  (HITL pause)
6. Human approved                  -> "persist_result"
7. Human rejected with feedback    -> "section_drafter"  (retry with feedback)
8. Review failed, iteration < max  -> "section_drafter"  (retry with feedback)
9. Review failed, iteration >= max -> "persist_result"   (give up, persist what we have)
"""

from __future__ import annotations

import logging
import time

from ..state import BidPilotState
from ._history import record_agent_call

logger = logging.getLogger(__name__)


def _llm_routing_decision(state: BidPilotState) -> str | None:
    """Use ChatOpenAI gpt-4o-mini for intelligent routing.

    Returns the target node name, or None if LLM call fails (triggering
    deterministic fallback).
    """
    import os

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.debug("No OPENAI_API_KEY — skipping LLM routing")
        return None

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=api_key)

        state_summary = (
            f"iteration={state.get('iteration', 0)}/{state.get('max_iterations', 3)}, "
            f"requirements_parsed={state.get('requirements_parsed', False)}, "
            f"evidence_retrieved={state.get('evidence_retrieved', False)}, "
            f"draft_created={state.get('draft_created', False)}, "
            f"review_passed={state.get('review_passed', False)}, "
            f"human_decision={state.get('human_decision')}, "
            f"error={state.get('error')}"
        )

        system_msg = (
            "You are a routing supervisor for a document drafting pipeline. "
            "Given the current state, choose the NEXT node to execute.\n\n"
            "Available nodes:\n"
            "- rfp_parser: Extract requirements from source documents\n"
            "- knowledge_retriever: Retrieve relevant evidence chunks\n"
            "- section_drafter: Generate draft using LLM\n"
            "- quality_reviewer: Review draft quality\n"
            "- human_approval: Pause for human review (HITL)\n"
            "- persist_result: Save final result to database\n\n"
            "Rules:\n"
            "- If requirements not parsed -> rfp_parser\n"
            "- If evidence not retrieved -> knowledge_retriever\n"
            "- If draft not created -> section_drafter\n"
            "- If draft exists but not reviewed -> quality_reviewer\n"
            "- If review passed and human hasn't decided -> human_approval\n"
            "- If human approved -> persist_result\n"
            "- If human rejected with feedback -> section_drafter\n"
            "- If review failed and iteration < max -> section_drafter\n"
            "- If review failed and iteration >= max -> persist_result\n\n"
            "Return ONLY the node name, nothing else."
        )

        response = llm.invoke([
            SystemMessage(content=system_msg),
            HumanMessage(content=f"Current state:\n{state_summary}"),
        ])

        target = response.content.strip().lower().strip('"')

        valid_targets = {
            "rfp_parser",
            "knowledge_retriever",
            "section_drafter",
            "quality_reviewer",
            "human_approval",
            "persist_result",
        }

        if target in valid_targets:
            logger.info("LLM routing decision: %s", target)
            return target

        logger.warning("LLM returned invalid target: %s — falling back", target)
        return None

    except Exception as exc:
        logger.warning("LLM routing failed: %s — falling back to deterministic", exc)
        return None


def _deterministic_routing(state: BidPilotState) -> str:
    """Deterministic state-inspection routing (fallback).

    Checks state flags in priority order to decide the next node.
    """
    # State flag checks in priority order
    if not state.get("requirements_parsed"):
        return "rfp_parser"

    if not state.get("evidence_retrieved"):
        return "knowledge_retriever"

    if not state.get("draft_created"):
        return "section_drafter"

    if not state.get("review_passed") and state.get("review_result") is None:
        return "quality_reviewer"

    # HITL resume: review passed but human hasn't decided yet
    if state.get("review_passed") and state.get("human_decision") is None:
        return "human_approval"

    # HITL completed: route based on human decision
    if state.get("human_decision") == "rejected_with_feedback":
        return "section_drafter"

    return "persist_result"


def supervisor_node(state: BidPilotState) -> dict:
    """LangGraph node: intelligent routing with LLM + deterministic fallback.

    Uses ChatOpenAI gpt-4o-mini for routing decisions when available.
    Falls back to deterministic state inspection on LLM failure.

    Records routing decision to agent_history. Draft iteration is incremented
    by the section drafter node, not by routing.

    Returns:
        Partial state update with incremented ``iteration`` and
        ``agent_history`` record.
    """
    start = time.monotonic()
    current_iteration = state.get("iteration", 0)

    # Attempt LLM routing first
    llm_target = _llm_routing_decision(state)

    if llm_target:
        routing_method = "llm"
        target = llm_target
    else:
        routing_method = "deterministic"
        target = _deterministic_routing(state)

    duration_ms = int((time.monotonic() - start) * 1000)

    logger.info(
        "Supervisor routing (iteration %d/%d): method=%s target=%s",
        current_iteration,
        state.get("max_iterations", 3),
        routing_method,
        target,
    )

    # Build input summary
    input_summary = (
        f"iteration={current_iteration}/{state.get('max_iterations', 3)}, "
        f"parsed={state.get('requirements_parsed')}, "
        f"retrieved={state.get('evidence_retrieved')}, "
        f"draft={state.get('draft_created')}, "
        f"review_passed={state.get('review_passed')}, "
        f"human_decision={state.get('human_decision')}"
    )

    output_summary = (
        f"iteration={current_iteration}, "
        f"routing={routing_method}, "
        f"target={target}"
    )

    history = record_agent_call(
        agent="supervisor",
        action="route_decision",
        input_summary=input_summary,
        output_summary=output_summary,
        duration_ms=duration_ms,
        success=True,
    )

    return {
        "iteration": current_iteration,
        "agent_history": history,
    }


def route_after_review(state: BidPilotState) -> str:
    """Conditional edge: decide next node after quality review.

    When the review passes, route to ``human_approval`` so a human can
    approve or reject the draft before persistence.

    Returns the name of the next node to execute.
    """
    review_passed: bool = state.get("review_passed", False)
    iteration: int = state.get("iteration", 0)
    max_iterations: int = state.get("max_iterations", 3)

    if review_passed:
        logger.info("Review passed on iteration %d — routing to human approval", iteration)
        return "human_approval"

    if iteration < max_iterations:
        logger.info(
            "Review failed on iteration %d/%d — retrying draft",
            iteration,
            max_iterations,
        )
        return "section_drafter"

    logger.warning(
        "Review failed after %d iterations — persisting draft as-is",
        iteration,
    )
    return "persist_result"


def route_after_human_approval(state: BidPilotState) -> str:
    """Conditional edge: decide next node after human approval.

    On resume from the interrupt:
    - "approved"             -> persist the result
    - "rejected_with_feedback" -> re-draft with the human's feedback

    Falls back to persist_result for any unexpected decision value.
    """
    decision: str = state.get("human_decision", "approved")
    section_key: str = state.get("section_key", "")

    if decision == "approved":
        logger.info("Human approved draft for %s — persisting", section_key)
        return "persist_result"

    if decision == "rejected_with_feedback":
        feedback = state.get("human_feedback", "")
        logger.info(
            "Human rejected draft for %s — re-drafting with feedback (%d chars)",
            section_key,
            len(feedback) if feedback else 0,
        )
        return "section_drafter"

    logger.warning(
        "Unexpected human_decision=%r for %s — persisting as-is",
        decision,
        section_key,
    )
    return "persist_result"


def route_initial(state: BidPilotState) -> str:
    """Conditional edge: decide the first node based on what data is missing.

    This is the routing function used by the supervisor's conditional edge.
    Delegates to _deterministic_routing for consistency.
    """
    return _deterministic_routing(state)


def route_after_rfp(state: BidPilotState) -> str:
    """Conditional edge: after RFP parsing, go retrieve evidence."""
    return "knowledge_retriever"


def route_after_retrieval(state: BidPilotState) -> str:
    """Conditional edge: after knowledge retrieval, go draft."""
    return "section_drafter"


def route_after_draft(state: BidPilotState) -> str:
    """Conditional edge: after drafting, go to quality review."""
    return "quality_reviewer"
