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
from app.retrieval.evidence_sets import EvidenceSetScopeError, load_authorized_evidence_set
from app.runtime.events import publish_provider_retry
from contracts.response_plans import (
    ResponsePlanScopeError,
    load_authorized_response_plan_binding,
)
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


def _append_content_plan(
    system_prompt: str | None,
    state: BidPilotState,
    *,
    content_plan: dict | None = None,
) -> str | None:
    """Inject the pre-draft content plan as trusted writing structure."""
    plan = content_plan if content_plan is not None else state.get("content_plan")
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


def _load_authorized_evidence(state: BidPilotState) -> tuple[list[dict], dict]:
    """Reload the durable evidence snapshot instead of trusting graph state."""
    evidence_set_id = state.get("evidence_set_id")
    if not isinstance(evidence_set_id, str) or not evidence_set_id:
        # Compatibility for direct unit-node invocation. Product graph runs
        # always receive an EvidenceSet from knowledge_retriever.
        return list(state.get("evidence_chunks") or []), {}

    db = SessionLocal()
    try:
        snapshot = load_authorized_evidence_set(
            db,
            evidence_set_id=evidence_set_id,
            project_id=state["project_id"],
            execution_run_id=state["run_id"],
        )
        if snapshot.status == "invalidated":
            db.commit()
            raise EvidenceSetScopeError("evidence_set_invalidated")
        db.commit()
        return (
            snapshot.evidence_chunks,
            {
                "evidence_set_id": snapshot.id,
                "evidence_set_status": snapshot.status,
                "evidence_set_unmet_requirement_ids": list(snapshot.unmet_requirement_ids),
                "evidence_set_degraded_reasons": list(
                    dict.fromkeys([*snapshot.degraded_reasons, *snapshot.rejected_reasons])
                ),
            },
        )
    finally:
        db.close()


def _load_authorized_response_plan(state: BidPilotState) -> tuple[dict | None, list[dict], dict]:
    """Reload the immutable plan snapshot instead of trusting graph state."""
    binding_id = state.get("response_plan_evidence_binding_id")
    if not isinstance(binding_id, str) or not binding_id:
        # Compatibility for direct unit-node invocation. Product graph runs
        # always create a response-plan binding after retrieval.
        plan = state.get("content_plan")
        return (plan if isinstance(plan, dict) else None, list(state.get("requirements") or []), {})

    db = SessionLocal()
    try:
        snapshot = load_authorized_response_plan_binding(
            db,
            response_plan_evidence_binding_id=binding_id,
            project_id=state["project_id"],
            execution_run_id=state["run_id"],
            section_key=state["section_key"],
        )
        return (
            snapshot.content_plan,
            list(snapshot.requirements),
            {
                "response_plan_id": snapshot.response_plan_id,
                "response_plan_section_id": snapshot.response_plan_section_id,
                "response_plan_evidence_binding_id": (
                    snapshot.response_plan_evidence_binding_id
                ),
                "response_plan_version": snapshot.response_plan_version,
            },
        )
    finally:
        db.close()


def _append_evidence_set_guard(
    system_prompt: str | None,
    *,
    evidence_chunks: list[dict],
    evidence_set_id: str | None,
    evidence_set_status: str | None,
) -> str | None:
    """Tell the model exactly which durable evidence boundary it may use."""
    if not evidence_set_id:
        return system_prompt
    lines = [
        system_prompt or "你是投标方案起草助手。",
        "\n本次草拟只能使用系统已授权的证据集。不得臆造来源、页码、文件名或引用。",
    ]
    if not evidence_chunks:
        lines.append(
            "当前没有仍然有效的授权证据。只能给出待补充资料的结构性草稿，"
            "不得把计划、记忆或常识写成已被来源证实的事实。"
        )
        return "\n".join(lines)

    lines.append("可用证据定位：")
    for index, chunk in enumerate(evidence_chunks, start=1):
        locator = chunk.get("locator_json") if isinstance(chunk.get("locator_json"), dict) else {}
        location: list[str] = []
        if isinstance(locator.get("page"), int):
            location.append(f"第 {locator['page']} 页")
        if isinstance(locator.get("heading"), str) and locator["heading"].strip():
            location.append(locator["heading"].strip()[:120])
        location.append(f"片段 {locator.get('chunk_index', chunk.get('chunk_index', 0))}")
        lines.append(f"- E{index}: {' / '.join(location)}")
    if evidence_set_status in {"degraded", "invalidated", "missing_evidence"}:
        lines.append("证据集存在降级或缺口；任何未被上列证据直接支持的内容必须明确标为待确认。")
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
    iteration: int = state.get("iteration", 0)
    run_id = state.get("run_id")
    if not isinstance(run_id, str):
        run_id = None
    attempt_tracker: dict[str, object] = {}

    provider_type = "openai"
    evidence_state_update: dict = {}
    response_plan_state_update: dict = {}

    try:
        evidence_chunks, evidence_state_update = _load_authorized_evidence(state)
        durable_content_plan, _durable_requirements, response_plan_state_update = (
            _load_authorized_response_plan(state)
        )
        evidence_texts = [
            chunk["content"]
            for chunk in evidence_chunks
            if isinstance(chunk.get("content"), str)
        ]
        provider_config_dict, provider_type = _resolve_provider(provider_config_id)
        system_prompt = _append_evidence_set_guard(
            _append_content_plan(
                _append_memory_context(_load_system_prompt(project_id), state),
                state,
                content_plan=durable_content_plan,
            ),
            evidence_chunks=evidence_chunks,
            evidence_set_id=(
                evidence_state_update.get("evidence_set_id")
                if isinstance(evidence_state_update.get("evidence_set_id"), str)
                else state.get("evidence_set_id")
            ),
            evidence_set_status=(
                evidence_state_update.get("evidence_set_status")
                if isinstance(evidence_state_update.get("evidence_set_status"), str)
                else state.get("evidence_set_status")
            ),
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
            **evidence_state_update,
            **response_plan_state_update,
            "evidence_chunks": evidence_chunks,
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
    except (EvidenceSetScopeError, ResponsePlanScopeError) as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        failure_code = (
            "evidence_set_unavailable"
            if isinstance(exc, EvidenceSetScopeError)
            else "response_plan_unavailable"
        )
        if run_id:
            finalize_workflow_model_reservation_failure(
                run_id=run_id,
                error_code=failure_code,
            )
        history = record_agent_call(
            agent="section_drafter",
            action="draft_section",
            input_summary=f"section={section_key}, durable_plan_or_evidence=unavailable",
            output_summary=f"ERROR: {failure_code}",
            duration_ms=duration_ms,
            success=False,
            error=failure_code,
        )
        return {
            "draft_markdown": "",
            "draft_model_used": "",
            "draft_created": False,
            "iteration": iteration + 1,
            "provider_error_code": failure_code,
            "error": "section_drafter: 本次草拟的计划或证据集已不可用，请重新发起工作流。",
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
