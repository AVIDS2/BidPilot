"""Section drafter node: generate draft content via LLM with retry.

Wraps the existing OpenAI / Anthropic adapter calls behind a tenacity
retry decorator (3 attempts, exponential backoff).  Reads
``provider_config_id`` from state to honour user-specific provider
settings.
"""

from __future__ import annotations

import logging
import time

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.adapters.llm import draft_section as draft_section_openai
from app.adapters.llm import DraftResult
from app.adapters.anthropic_llm import draft_section as draft_section_anthropic
from app.adapters.provider_errors import ProviderInvocationError
from app.adapters.structured_llm import resolve_structured_provider
from app.db import SessionLocal
from app.models import Project
from app.runtime.events import publish_provider_retry
from app.execution.model_usage import (
    begin_workflow_model_call,
    finalize_workflow_model_reservation_failure,
    mark_workflow_model_call_uncertain,
    record_workflow_model_usage,
)

from ..state import BidPilotState
from ._history import record_agent_call

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3


class DraftError(Exception):
    """Raised when all LLM draft attempts are exhausted."""


def _is_retryable_provider_error(exc: BaseException) -> bool:
    return isinstance(exc, ProviderInvocationError) and exc.retryable


def _publish_provider_retry(retry_state) -> None:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if not isinstance(exc, ProviderInvocationError):
        return
    run_id = retry_state.kwargs.get("run_id")
    tracker = retry_state.kwargs.get("attempt_tracker")
    reservation_key = tracker.get("reservation_key") if isinstance(tracker, dict) else None
    if isinstance(run_id, str) and run_id:
        mark_workflow_model_call_uncertain(
            run_id=run_id,
            reservation_key=reservation_key if isinstance(reservation_key, str) else None,
        )
    publish_provider_retry(
        retry_state.kwargs.get("runtime_run_id"),
        node_name="section_drafter",
        error_code=exc.error_code,
        next_attempt=retry_state.attempt_number + 1,
        max_attempts=_MAX_ATTEMPTS,
    )


def _prepare_provider_attempt(retry_state) -> None:
    """Commit a durable hold before every physical provider dispatch."""
    attempt_number = retry_state.attempt_number
    tracker = retry_state.kwargs.get("attempt_tracker")
    if isinstance(tracker, dict):
        tracker["attempt"] = attempt_number

    run_id = retry_state.kwargs.get("run_id")
    draft_iteration = retry_state.kwargs.get("draft_iteration", 0)
    if not isinstance(run_id, str) or not run_id:
        return
    if not isinstance(draft_iteration, int):
        draft_iteration = 0
    call = begin_workflow_model_call(
        run_id=run_id,
        workload="workflow_draft",
        operation_key=f"draft-{draft_iteration + 1}-attempt-{attempt_number}",
    )
    if isinstance(tracker, dict):
        tracker["reservation_key"] = call.reservation_key


@retry(
    stop=stop_after_attempt(_MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception(_is_retryable_provider_error),
    reraise=True,
    before=_prepare_provider_attempt,
    before_sleep=_publish_provider_retry,
)
def _draft_with_retry(
    section_key: str,
    evidence_texts: list[str],
    project_id: str,
    review_feedback: str | None,
    system_prompt: str | None,
    provider_config_dict: dict | None,
    provider_type: str,
    reasoning_effort: str | None,
    runtime_run_id: str | None,
    run_id: str | None = None,
    draft_iteration: int = 0,
    attempt_tracker: dict[str, object] | None = None,
) -> DraftResult:
    """Call the appropriate LLM adapter with tenacity retry.

    Raises on failure after all retries are exhausted so the caller can
    record the error in state.
    """
    if provider_type == "anthropic":
        return draft_section_anthropic(
            section_key,
            evidence_texts,
            project_id,
            review_feedback=review_feedback,
            system_prompt=system_prompt,
            provider_config=provider_config_dict,
            reasoning_effort=reasoning_effort,
        )
    return draft_section_openai(
        section_key,
        evidence_texts,
        project_id,
        review_feedback=review_feedback,
        system_prompt=system_prompt,
        provider_config=provider_config_dict,
        reasoning_effort=reasoning_effort,
    )


def _resolve_provider(provider_config_id: str | None) -> tuple[dict | None, str]:
    """Use the same authorized provider selection path as all workflow nodes."""
    provider_config, provider_type = resolve_structured_provider(provider_config_id)
    return provider_config, provider_type


def _load_system_prompt(project_id: str) -> str | None:
    """Load scenario-specific system prompt from the project."""
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project and project.scenario_package:
            try:
                from app.scenarios.templates import get_drafting_prompt

                return get_drafting_prompt(project.scenario_package)
            except Exception:
                pass
        return None
    finally:
        db.close()


def _append_memory_context(system_prompt: str | None, state: BidPilotState) -> str | None:
    items = state.get("memory_context_items", [])
    if not items:
        return system_prompt
    lines = [
        system_prompt or "你是投标方案起草助手。",
        "\n已授权的长期记忆仅作工作偏好和已审核背景参考；事实性表述仍必须由检索证据支撑：",
    ]
    for item in items:
        citations = "；".join(item["citations"][:3])
        lines.append(
            f"- [{item['scope']}/{item['kind']}] {item['title']}: {item['body_markdown']}\n  来源：{citations}"
        )
    return "\n".join(lines)


def _append_content_plan(system_prompt: str | None, state: BidPilotState) -> str | None:
    """Inject the pre-draft content plan as trusted writing structure."""
    plan = state.get("content_plan")
    if not isinstance(plan, dict) or not plan:
        return system_prompt
    base = system_prompt or "你是投标方案起草助手。"
    lines = [
        base,
        "\n请严格按以下内容计划组织章节（计划由系统根据证据生成，不得编造未列证据）：",
        f"摘要：{plan.get('summary') or ''}",
    ]
    outline = plan.get("outline") or []
    if outline:
        lines.append("结构大纲：")
        lines.extend(f"- {item}" for item in outline[:8] if isinstance(item, str))
    key_points = plan.get("key_points") or []
    if key_points:
        lines.append("必须覆盖的要点：")
        lines.extend(f"- {item}" for item in key_points[:8] if isinstance(item, str))
    tables = plan.get("tables") or []
    if tables:
        lines.append("建议表格：")
        for item in tables[:4]:
            if isinstance(item, dict):
                lines.append(f"- {item.get('title')}: {item.get('detail')}")
    figures = plan.get("figures") or []
    if figures:
        lines.append("建议附图：")
        for item in figures[:3]:
            if isinstance(item, dict):
                lines.append(f"- {item.get('title')}: {item.get('detail')}")
    gaps = plan.get("gaps") or []
    if gaps:
        lines.append("已知缺口（需在正文中诚实标注）：")
        lines.extend(f"- {item}" for item in gaps[:4] if isinstance(item, str))
    return "\n".join(lines)


def section_drafter_node(state: BidPilotState) -> dict:
    """LangGraph node: draft a section using evidence and LLM.

    Reads evidence chunk contents from state, resolves the provider
    configuration, loads the scenario system prompt, and calls the LLM
    adapter with tenacity retry (3 attempts, exponential backoff).

    On success returns ``draft_markdown``, ``draft_model_used``,
    ``draft_created`` = True, and ``agent_history`` record.
    On failure after all retries returns an error string,
    ``draft_created`` = False, and ``agent_history`` record.

    Returns:
        Partial state update with drafting results.
    """
    start = time.monotonic()
    section_key: str = state["section_key"]
    project_id: str = state["project_id"]
    provider_config_id: str | None = state.get("provider_config_id")
    reasoning_effort: str | None = state.get("reasoning_effort")
    # Use human_feedback (from HITL) if available, otherwise input_review_feedback
    review_feedback: str | None = state.get("human_feedback") or state.get("input_review_feedback")
    evidence_chunks = state.get("evidence_chunks", [])
    iteration: int = state.get("iteration", 0)
    run_id = state.get("run_id")
    if not isinstance(run_id, str):
        run_id = None
    attempt_tracker: dict[str, object] = {}

    evidence_texts = [chunk["content"] for chunk in evidence_chunks]

    provider_type = "openai"

    try:
        provider_config_dict, provider_type = _resolve_provider(provider_config_id)
        system_prompt = _append_content_plan(
            _append_memory_context(_load_system_prompt(project_id), state),
            state,
        )
        result = _draft_with_retry(
            section_key=section_key,
            evidence_texts=evidence_texts,
            project_id=project_id,
            review_feedback=review_feedback,
            system_prompt=system_prompt,
            provider_config_dict=provider_config_dict,
            provider_type=provider_type,
            reasoning_effort=reasoning_effort,
            runtime_run_id=state.get("runtime_run_id"),
            run_id=run_id,
            draft_iteration=iteration,
            attempt_tracker=attempt_tracker,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "Drafted section %s with model %s (evidence=%d, iteration=%d)",
            section_key,
            result.model_used,
            len(evidence_texts),
            iteration,
        )
        if run_id:
            record_workflow_model_usage(
                run_id=run_id,
                provider_type=provider_type,
                model_name=result.model_used,
                measurement=result.usage,
                workload="workflow_draft",
                reservation_key=(
                    attempt_tracker.get("reservation_key")
                    if isinstance(attempt_tracker.get("reservation_key"), str)
                    else None
                ),
            )

        history = record_agent_call(
            agent="section_drafter",
            action="draft_section",
            input_summary=(
                f"section={section_key}, evidence={len(evidence_texts)}, "
                f"iteration={iteration}, provider={provider_type}, "
                f"has_feedback={review_feedback is not None}, "
                f"memory_records={len(state.get('memory_context_items', []))}"
            ),
            output_summary=(
                f"model={result.model_used}, draft_len={len(result.content_markdown)}, "
                f"draft_created=True"
            ),
            duration_ms=duration_ms,
            success=True,
        )

        return {
            "draft_markdown": result.content_markdown,
            "draft_model_used": result.model_used,
            "draft_created": True,
            "iteration": iteration + 1,
            # Clear stale review/HITL fields whenever a new draft revision starts.
            # Otherwise resume/retry can keep a previous review_passed=True and
            # skip quality review or re-enter human approval incorrectly.
            "review_result": None,
            "review_passed": False,
            "human_decision": None,
            "agent_history": history,
        }
    except ProviderInvocationError as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.warning(
            "section_drafter provider failure for section %s: %s",
            section_key,
            exc.error_code,
        )
        if run_id:
            finalize_workflow_model_reservation_failure(
                run_id=run_id,
                error_code=exc.error_code,
            )

        history = record_agent_call(
            agent="section_drafter",
            action="draft_section",
            input_summary=(
                f"section={section_key}, evidence={len(evidence_texts)}, "
                f"iteration={iteration}, provider={provider_type}"
            ),
            output_summary=f"ERROR: {exc.error_code}",
            duration_ms=duration_ms,
            success=False,
            error=exc.error_code,
        )

        return {
            "draft_markdown": "",
            "draft_model_used": "",
            "draft_created": False,
            "iteration": iteration + 1,
            "provider_error_code": exc.error_code,
            "error": f"section_drafter: {exc.public_message}",
            "agent_history": history,
        }
    except Exception:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.exception("section_drafter_node failed for section %s", section_key)
        if run_id:
            finalize_workflow_model_reservation_failure(
                run_id=run_id,
                error_code="workflow_internal_error",
            )
        public_message = "章节起草遇到内部错误，请稍后重试。"

        history = record_agent_call(
            agent="section_drafter",
            action="draft_section",
            input_summary=(
                f"section={section_key}, evidence={len(evidence_texts)}, "
                f"iteration={iteration}, provider={provider_type}"
            ),
            output_summary="ERROR: workflow_internal_error",
            duration_ms=duration_ms,
            success=False,
            error="workflow_internal_error",
        )

        return {
            "draft_markdown": "",
            "draft_model_used": "",
            "draft_created": False,
            "iteration": iteration + 1,
            "provider_error_code": "workflow_internal_error",
            "error": f"section_drafter: {public_message}",
            "agent_history": history,
        }
