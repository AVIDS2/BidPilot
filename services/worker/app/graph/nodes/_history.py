"""Agent history tracking utilities.

Provides a decorator and helper to record agent node invocations into
the ``agent_history`` field of BidPilotState with automatic timing.
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable

from ..state import AgentCall

logger = logging.getLogger(__name__)


def _truncate(text: str, max_len: int = 200) -> str:
    """Truncate text to max_len characters, adding ellipsis if needed."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def record_agent_call(
    agent: str,
    action: str,
    input_summary: str,
    output_summary: str,
    duration_ms: int,
    success: bool,
    error: str | None = None,
) -> list[AgentCall]:
    """Create a single-element list containing an AgentCall record.

    This is designed to be returned alongside other state fields so that
    LangGraph's ``operator.add`` reducer appends it to ``agent_history``.
    """
    return [
        AgentCall(
            agent=agent,
            action=action,
            input_summary=_truncate(input_summary),
            output_summary=_truncate(output_summary),
            duration_ms=duration_ms,
            success=success,
            error=error,
        )
    ]


def with_history(
    agent_name: str,
    action: str,
) -> Callable:
    """Decorator that wraps a node function with agent history tracking.

    Measures execution time, catches exceptions, and appends an AgentCall
    record to the returned state dict's ``agent_history`` list.

    Usage::

        @with_history("rfp_parser", "extract_requirements")
        def rfp_parser_node(state: BidPilotState) -> dict:
            ...
            return {"requirements": reqs, "requirements_parsed": True, ...}
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(state: dict) -> dict:
            start = time.monotonic()
            try:
                result = fn(state)
                duration_ms = int((time.monotonic() - start) * 1000)

                # Build summaries from input/output
                input_summary = _build_input_summary(state, agent_name)
                output_summary = _build_output_summary(result, agent_name)

                # Append history record via operator.add
                history = record_agent_call(
                    agent=agent_name,
                    action=action,
                    input_summary=input_summary,
                    output_summary=output_summary,
                    duration_ms=duration_ms,
                    success=True,
                )
                result["agent_history"] = history
                return result

            except Exception as exc:
                duration_ms = int((time.monotonic() - start) * 1000)
                logger.exception("%s node failed", agent_name)

                history = record_agent_call(
                    agent=agent_name,
                    action=action,
                    input_summary=_build_input_summary(state, agent_name),
                    output_summary=f"ERROR: {exc}",
                    duration_ms=duration_ms,
                    success=False,
                    error=str(exc),
                )
                # Return a minimal state update with the error history
                return {"agent_history": history, "error": f"{agent_name}: {exc}"}

        return wrapper

    return decorator


def _build_input_summary(state: dict, agent_name: str) -> str:
    """Build a brief summary of the inputs relevant to this agent."""
    summaries = {
        "supervisor": lambda s: (
            f"iteration={s.get('iteration', 0)}/{s.get('max_iterations', 3)}, "
            f"parsed={s.get('requirements_parsed')}, retrieved={s.get('evidence_retrieved')}, "
            f"draft={s.get('draft_created')}, review_passed={s.get('review_passed')}"
        ),
        "rfp_parser": lambda s: f"project_id={s.get('project_id')}, section={s.get('section_key')}",
        "knowledge_retriever": lambda s: (
            f"project_id={s.get('project_id')}, section={s.get('section_key')}, "
            f"requirements={len(s.get('requirements', []))}"
        ),
        "section_drafter": lambda s: (
            f"section={s.get('section_key')}, evidence={len(s.get('evidence_chunks', []))}, "
            f"has_feedback={s.get('human_feedback') is not None or s.get('input_review_feedback') is not None}"
        ),
        "quality_reviewer": lambda s: (
            f"section={s.get('section_key')}, draft_len={len(s.get('draft_markdown', ''))}, "
            f"iteration={s.get('iteration', 0)}"
        ),
        "human_approval": lambda s: (
            f"section={s.get('section_key')}, iteration={s.get('iteration', 0)}"
        ),
        "persist_result": lambda s: (
            f"section={s.get('section_key')}, run_id={s.get('run_id')}, "
            f"iteration={s.get('iteration', 0)}"
        ),
    }
    builder = summaries.get(agent_name)
    if builder:
        try:
            return builder(state)
        except Exception:
            pass
    return f"state_keys={list(state.keys())[:8]}"


def _build_output_summary(result: dict, agent_name: str) -> str:
    """Build a brief summary of the outputs from this agent."""
    parts = []
    for key, value in result.items():
        if key == "agent_history":
            continue
        if isinstance(value, bool):
            parts.append(f"{key}={value}")
        elif isinstance(value, str) and len(value) > 50:
            parts.append(f"{key}({len(value)}chars)")
        elif isinstance(value, list):
            parts.append(f"{key}[{len(value)}]")
        elif value is not None:
            parts.append(f"{key}={value}")
    return ", ".join(parts[:6]) if parts else "(empty)"
