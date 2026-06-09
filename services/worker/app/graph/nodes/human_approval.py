"""Human approval node: HITL pause/resume for the BidPilot graph.

When the graph reaches this node after a quality review passes, it calls
langgraph.types.interrupt() to pause execution and wait for human input.

On resume, the interrupt result contains:
- human_decision: "approved" or "rejected_with_feedback"
- human_feedback: optional feedback string when rejected

The node writes ``human_decision`` and ``human_feedback`` back into the
graph state so the supervisor can route accordingly.
"""

from __future__ import annotations

import logging
import time

from langgraph.types import interrupt

from ..state import BidPilotState
from ._history import record_agent_call

logger = logging.getLogger(__name__)


def human_approval_node(state: BidPilotState) -> dict:
    """LangGraph node: pause execution for human review.

    Calls ``interrupt()`` which halts the graph and surfaces a payload to
    the caller (API / UI).  The payload includes the draft content and
    review result so the human reviewer has full context.

    When the graph is resumed via ``graph.invoke(Command(resume=...), ...)``
    the ``interrupt()`` call returns the value the caller passed as the
    resume payload.

    Returns:
        Partial state update with ``human_decision``,
        ``human_feedback``, and ``agent_history`` record.
    """
    start = time.monotonic()
    section_key: str = state["section_key"]
    draft_markdown: str = state.get("draft_markdown", "")
    review_result = state.get("review_result")
    iteration: int = state.get("iteration", 0)

    # Build the payload surfaced to the human reviewer while paused.
    interrupt_payload = {
        "action": "human_approval_required",
        "section_key": section_key,
        "draft_preview": draft_markdown[:2000],
        "review_score": review_result.get("overall_score") if review_result else None,
        "review_issues": review_result.get("issues", []) if review_result else [],
        "iteration": iteration,
        "instructions": (
            "Review the draft and respond with a dict containing:\n"
            "  decision: 'approved' | 'rejected_with_feedback'\n"
            "  feedback: optional string with improvement notes"
        ),
    }

    # This pauses the graph.  On resume it returns the caller-supplied value.
    human_response = interrupt(interrupt_payload)

    # Parse the human response (may come as a dict or a pydantic model).
    if isinstance(human_response, dict):
        decision = human_response.get("decision", "approved")
        feedback = human_response.get("feedback")
    else:
        # Handle pydantic model or other object with attributes
        decision = getattr(human_response, "decision", "approved")
        feedback = getattr(human_response, "feedback", None)

    duration_ms = int((time.monotonic() - start) * 1000)

    logger.info(
        "Human approval for %s: decision=%s has_feedback=%s",
        section_key,
        decision,
        feedback is not None,
    )

    history = record_agent_call(
        agent="human_approval",
        action="human_review",
        input_summary=(
            f"section={section_key}, iteration={iteration}, "
            f"draft_len={len(draft_markdown)}, "
            f"review_score={review_result.get('overall_score') if review_result else None}"
        ),
        output_summary=(
            f"decision={decision}, "
            f"has_feedback={feedback is not None}, "
            f"feedback_len={len(feedback) if feedback else 0}"
        ),
        duration_ms=duration_ms,
        success=True,
    )

    return {
        "human_decision": decision,
        "human_feedback": feedback,
        "agent_history": history,
    }
