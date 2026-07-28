"""Quality review through the governed workflow model boundary."""

from __future__ import annotations

import json
import logging
import re
import time

from app.adapters.provider_errors import ProviderInvocationError
from app.adapters.structured_llm import (
    StructuredModelResult,
    invoke_structured_text,
    resolve_structured_provider,
)
from app.db import SessionLocal
from app.execution.model_usage import (
    begin_workflow_model_call,
    record_workflow_model_usage,
    resolve_workflow_model_call_failure,
)
from app.retrieval.evidence_sets import EvidenceSetScopeError, load_authorized_evidence_set
from contracts.untrusted_context import build_untrusted_context_packet
from contracts.response_plans import (
    ResponsePlanScopeError,
    load_authorized_response_plan_binding,
)

from ..state import BidPilotState, ClaimCandidate, ReviewResult
from ._history import record_agent_call

logger = logging.getLogger(__name__)

_MAX_DRAFT_CHARACTERS = 6_000
_MAX_REQUIREMENT_CONTEXT_CHARACTERS = 4_000
_MAX_EVIDENCE_CONTEXT_CHARACTERS = 3_000
_MAX_REVIEW_OUTPUT_TOKENS = 1_500
_MAX_CLAIM_CANDIDATES = 20
_MAX_CLAIM_CHARACTERS = 1_000
_SYSTEM_PROMPT = (
    "You are a quality reviewer for proposal documents. "
    "Evaluate the draft section against the given requirements. "
    "Return ONLY a JSON object with these exact keys:\n"
    "- passed: boolean (true if quality is acceptable)\n"
    "- issues: array of strings (specific problems found)\n"
    "- suggestions: array of strings (improvement recommendations)\n"
    "- overall_score: number 0.0-1.0 (quality score)\n"
    "- claims: array of grounded draft assertions, each with text, claim_type "
    "(factual or inference), requirement_refs (R aliases), and evidence_refs "
    "(E aliases)\n\n"
    "Be strict but fair. A draft should pass only if it addresses all "
    "high-priority requirements, uses evidence where available, has no "
    "glaring factual gaps, and is professionally structured. Only return a "
    "claim when text is a verbatim assertion from the draft and the supplied "
    "R/E aliases directly support it. Return an empty claims array when no "
    "grounded assertion can be identified."
)


def _build_review_prompt(
    section_key: str,
    draft_markdown: str,
    requirements: list[dict],
    evidence_chunks: list[dict],
) -> tuple[str, dict[str, str], dict[str, str]]:
    """Build bounded review context and server-only alias maps."""
    context_records: list[dict[str, object]] = []
    requirement_refs: dict[str, str] = {}
    used = 0
    for requirement in requirements:
        requirement_section = str(requirement.get("section_key") or "")
        if requirement_section and requirement_section not in {section_key, "extracted"}:
            continue
        marker = "[HIGH]" if requirement.get("priority") == "high" else "[NORMAL]"
        requirement_id = requirement.get("id")
        alias = ""
        if isinstance(requirement_id, str) and requirement_id:
            alias = f"R{len(requirement_refs) + 1}"
            requirement_refs[alias] = requirement_id
        requirement_text = str(requirement.get("requirement_text") or "")[:500]
        if used + len(requirement_text) > _MAX_REQUIREMENT_CONTEXT_CHARACTERS:
            break
        context_records.append(
            {
                "kind": "requirement",
                "alias": alias,
                "priority": marker,
                "content": requirement_text,
            }
        )
        used += len(requirement_text)

    evidence_refs: dict[str, str] = {}
    used = 0
    for chunk in evidence_chunks:
        chunk_id = chunk.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id:
            continue
        alias = f"E{len(evidence_refs) + 1}"
        evidence_text = str(chunk.get("content") or "")[:300]
        if used + len(evidence_text) > _MAX_EVIDENCE_CONTEXT_CHARACTERS:
            break
        evidence_refs[alias] = chunk_id
        context_records.append({"kind": "evidence", "alias": alias, "content": evidence_text})
        used += len(evidence_text)

    context_records.append(
        {
            "kind": "draft",
            "section_key": section_key[:120],
            "content": draft_markdown[:_MAX_DRAFT_CHARACTERS],
        }
    )
    packet = build_untrusted_context_packet("quality_review", context_records)

    prompt = (
        "Evaluate the draft and return the JSON review object. Requirement and "
        "evidence aliases from UNTRUSTED_CONTEXT_JSON must be used exactly in "
        "claim references.\n\n"
        "UNTRUSTED_CONTEXT_JSON:\n"
        f"{packet}"
    )
    return prompt, requirement_refs, evidence_refs


def _parse_review(
    result: StructuredModelResult,
    *,
    draft_markdown: str,
    requirement_refs: dict[str, str],
    evidence_refs: dict[str, str],
) -> tuple[ReviewResult, list[ClaimCandidate]]:
    match = re.search(r"\{.*\}", result.content, re.DOTALL)
    if not match:
        raise ProviderInvocationError(
            "provider_response_invalid",
            "模型服务未返回可解析的审核结果，正在按策略降级处理。",
            retryable=True,
        )
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as exc:
        raise ProviderInvocationError(
            "provider_response_invalid",
            "模型服务未返回可解析的审核结果，正在按策略降级处理。",
            retryable=True,
        ) from exc
    if not isinstance(data, dict):
        raise ProviderInvocationError(
            "provider_response_invalid",
            "模型服务未返回可解析的审核结果，正在按策略降级处理。",
            retryable=True,
        )
    try:
        score = float(data.get("overall_score", 0.0))
    except (TypeError, ValueError):
        score = 0.0
    issues = data.get("issues", [])
    suggestions = data.get("suggestions", [])
    if not isinstance(issues, list):
        issues = []
    if not isinstance(suggestions, list):
        suggestions = []
    review = ReviewResult(
        passed=bool(data.get("passed", False)),
        issues=[str(issue)[:500] for issue in issues if isinstance(issue, (str, int, float))],
        suggestions=[
            str(suggestion)[:500]
            for suggestion in suggestions
            if isinstance(suggestion, (str, int, float))
        ],
        overall_score=max(0.0, min(score, 1.0)),
    )
    return review, _parse_claim_candidates(
        data.get("claims"),
        draft_markdown=draft_markdown,
        requirement_refs=requirement_refs,
        evidence_refs=evidence_refs,
    )


def _parse_claim_candidates(
    raw_claims: object,
    *,
    draft_markdown: str,
    requirement_refs: dict[str, str],
    evidence_refs: dict[str, str],
) -> list[ClaimCandidate]:
    """Accept only exact draft assertions tied to this review's aliases."""
    if not isinstance(raw_claims, list):
        return []
    normalized_draft = _normalize_claim_text(draft_markdown)
    candidates: list[ClaimCandidate] = []
    seen: set[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = set()
    for raw_claim in raw_claims[:_MAX_CLAIM_CANDIDATES]:
        if not isinstance(raw_claim, dict):
            continue
        claim_text = raw_claim.get("text")
        claim_type = raw_claim.get("claim_type")
        if (
            not isinstance(claim_text, str)
            or not isinstance(claim_type, str)
            or claim_type not in {"factual", "inference"}
        ):
            continue
        claim_text = claim_text.strip()
        normalized_claim = _normalize_claim_text(claim_text)
        if (
            len(claim_text) < 3
            or len(claim_text) > _MAX_CLAIM_CHARACTERS
            or not normalized_claim
            or normalized_claim not in normalized_draft
        ):
            continue
        requirement_aliases = _unique_aliases(raw_claim.get("requirement_refs"))
        evidence_aliases = _unique_aliases(raw_claim.get("evidence_refs"))
        if (
            not requirement_aliases
            or not evidence_aliases
            or not set(requirement_aliases).issubset(requirement_refs)
            or not set(evidence_aliases).issubset(evidence_refs)
        ):
            continue
        requirement_ids = [requirement_refs[alias] for alias in requirement_aliases]
        evidence_chunk_ids = [evidence_refs[alias] for alias in evidence_aliases]
        candidate_key = (
            normalized_claim,
            claim_type,
            tuple(requirement_ids),
            tuple(evidence_chunk_ids),
        )
        if candidate_key in seen:
            continue
        seen.add(candidate_key)
        candidates.append(
            ClaimCandidate(
                claim_text=claim_text,
                claim_type=claim_type,
                requirement_ids=requirement_ids,
                evidence_chunk_ids=evidence_chunk_ids,
            )
        )
    return candidates


def _unique_aliases(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    aliases: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item or item in aliases:
            continue
        aliases.append(item)
    return aliases


def _normalize_claim_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _deterministic_review(state: BidPilotState) -> ReviewResult:
    """Safe, inspectable fallback when model review cannot complete."""
    draft = state.get("draft_markdown", "")
    evidence = state.get("evidence_chunks", [])
    requirements = state.get("requirements", [])
    high_requirements = [item for item in requirements if item.get("priority") == "high"]
    issues: list[str] = []
    suggestions: list[str] = []
    if not draft.strip():
        issues.append("Draft is empty")
    if len(draft.strip()) < 200:
        issues.append("Draft is too short (< 200 characters)")
    if not evidence:
        issues.append("No evidence chunks were retrieved")
    if high_requirements and draft.strip():
        suggestions.append("Verify all high-priority requirements are addressed")
    return ReviewResult(
        passed=not issues,
        issues=issues,
        suggestions=suggestions,
        overall_score=max(0.0, 1.0 - len(issues) * 0.25),
    )


def _load_authorized_evidence_for_review(state: BidPilotState) -> tuple[list[dict], dict]:
    """Reload the persisted evidence boundary before evaluating factual claims."""
    evidence_set_id = state.get("evidence_set_id")
    if not isinstance(evidence_set_id, str) or not evidence_set_id:
        # Compatibility for direct unit-node invocation. Production graph runs
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


def _load_authorized_plan_requirements(state: BidPilotState) -> tuple[list[dict], dict]:
    """Review only the persisted requirements assigned to this plan section."""
    binding_id = state.get("response_plan_evidence_binding_id")
    if not isinstance(binding_id, str) or not binding_id:
        # Compatibility for direct unit-node invocation. Product graph runs
        # always create a response-plan binding before the draft node.
        return list(state.get("requirements") or []), {}

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


def quality_reviewer_node(state: BidPilotState) -> dict:
    """Review a draft with a governed model call and deterministic fallback."""
    start = time.monotonic()
    section_key: str = state["section_key"]
    draft_markdown: str = state.get("draft_markdown", "")
    requirements = state.get("requirements", [])
    provider_config_id: str | None = state.get("provider_config_id")
    reasoning_effort: str | None = state.get("reasoning_effort")
    iteration: int = state.get("iteration", 0)
    run_id = state.get("run_id")
    call_reservation_key: str | None = None
    review_method = "deterministic"
    degradation_code: str | None = None
    claim_candidates: list[ClaimCandidate] = []
    claim_integrity_status = "not_applicable"
    evidence_chunks: list[dict] = []
    evidence_state_update: dict = {}
    response_plan_state_update: dict = {}

    try:
        evidence_chunks, evidence_state_update = _load_authorized_evidence_for_review(state)
        requirements, response_plan_state_update = _load_authorized_plan_requirements(state)
        provider_config, provider_type = resolve_structured_provider(provider_config_id)
        if isinstance(run_id, str) and run_id:
            call = begin_workflow_model_call(
                run_id=run_id,
                workload="workflow_quality_review",
                operation_key=f"quality-review-{iteration}",
            )
            call_reservation_key = call.reservation_key
        review_prompt, requirement_refs, evidence_refs = _build_review_prompt(
            section_key=section_key,
            draft_markdown=draft_markdown,
            requirements=requirements,
            evidence_chunks=evidence_chunks,
        )
        result = invoke_structured_text(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=review_prompt,
            provider_config=provider_config,
            provider_type=provider_type,
            max_output_tokens=_MAX_REVIEW_OUTPUT_TOKENS,
            temperature=0.2,
            reasoning_effort=reasoning_effort,
        )
        review, claim_candidates = _parse_review(
            result,
            draft_markdown=draft_markdown,
            requirement_refs=requirement_refs,
            evidence_refs=evidence_refs,
        )
        if isinstance(run_id, str) and run_id:
            record_workflow_model_usage(
                run_id=run_id,
                provider_type=result.provider_type,
                model_name=result.model_used,
                measurement=result.usage,
                workload="workflow_quality_review",
                reservation_key=call_reservation_key,
        )
        review_method = "llm"
        claim_integrity_status = (
            "proposed"
            if claim_candidates
            else "no_grounded_candidates"
            if requirement_refs and evidence_refs
            else "not_applicable"
        )
    except (EvidenceSetScopeError, ResponsePlanScopeError) as exc:
        review = ReviewResult(
            passed=False,
            issues=["Authorized evidence set or response plan is unavailable"],
            suggestions=["Restart the workflow after retrieving current project evidence."],
            overall_score=0.0,
        )
        degradation_code = (
            "evidence_set_unavailable"
            if isinstance(exc, EvidenceSetScopeError)
            else "response_plan_unavailable"
        )
        claim_integrity_status = "invalid_evidence_set" if isinstance(exc, EvidenceSetScopeError) else "invalid_response_plan"
    except ProviderInvocationError as exc:
        if isinstance(run_id, str) and run_id:
            resolve_workflow_model_call_failure(
                run_id=run_id,
                reservation_key=call_reservation_key,
                error_code=exc.error_code,
            )
        logger.warning("Quality review degraded: code=%s", exc.error_code)
        review = _deterministic_review(
            {**state, "evidence_chunks": evidence_chunks, "requirements": requirements}
        )
        degradation_code = exc.error_code
        claim_integrity_status = "degraded"

    duration_ms = int((time.monotonic() - start) * 1000)
    output = (
        f"passed={review['passed']}, score={review['overall_score']:.2f}, "
        f"issues[{len(review['issues'])}], suggestions[{len(review['suggestions'])}], "
        f"claims[{len(claim_candidates)}], integrity={claim_integrity_status}"
    )
    if degradation_code:
        output = f"{output}, degraded={degradation_code}"
    history = record_agent_call(
        agent="quality_reviewer",
        action="review_draft",
        input_summary=(
            f"section={section_key}, draft_len={len(draft_markdown)}, "
            f"requirements={len(requirements)}, evidence={len(evidence_chunks)}, "
            f"iteration={iteration}, method={review_method}, claims={len(claim_candidates)}"
        ),
        output_summary=output,
        duration_ms=duration_ms,
        success=True,
    )
    return {
        **evidence_state_update,
        **response_plan_state_update,
        "evidence_chunks": evidence_chunks,
        "review_result": review,
        "review_passed": review["passed"],
        "claim_candidates": claim_candidates,
        "claim_integrity_status": claim_integrity_status,
        "error": (
            "quality_reviewer: 本次草拟的计划或证据集已不可用，请重新发起工作流。"
            if degradation_code in {"evidence_set_unavailable", "response_plan_unavailable"}
            else state.get("error")
        ),
        "agent_history": history,
    }
