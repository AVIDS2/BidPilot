"""Extract durable proposal requirements through the governed model boundary."""

from __future__ import annotations

import json
import logging
import re
import time

from sqlalchemy import select

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
from app.models import Bundle, ParsedAsset, Project, RequirementItem, SourceDocument
from app.scenarios.registry import get_scenario_or_raise
from contracts.untrusted_context import build_untrusted_context_packet

from ..state import BidPilotState, Requirement
from ._history import record_agent_call

logger = logging.getLogger(__name__)

_MAX_RFP_SOURCE_CHARACTERS = 12_000
_MAX_REQUIREMENT_OUTPUT_TOKENS = 3_000
_SYSTEM_PROMPT = (
    "You are a requirements analyst. Extract structured requirements from "
    "documents. Return only a valid JSON array of objects with keys: "
    "section_key (kebab-case), requirement_text, priority (high/normal/low)."
)
_KEYWORDS_DEFAULT = ["shall", "must", "should", "required", "mandatory", "necessary"]


def _build_user_prompt(text: str, keywords: list[str]) -> str:
    kw_list = ", ".join(keywords)
    packet = build_untrusted_context_packet(
        "requirement_extraction",
        ({"kind": "source_document", "content": text[:_MAX_RFP_SOURCE_CHARACTERS]},),
    )
    return (
        "Extract structured requirements from the source data in UNTRUSTED_CONTEXT_JSON.\n"
        "For each requirement:\n"
        "- section_key: a short kebab-case identifier for the section it belongs to\n"
        "- requirement_text: the full requirement text\n"
        '- priority: "high" for mandatory/shall/must, "normal" for should/recommended, '
        '"low" for optional/may\n\n'
        f"Focus especially on keywords: {kw_list}\n\n"
        "Return as a JSON array.\n\n"
        "UNTRUSTED_CONTEXT_JSON:\n"
        f"{packet}"
    )


def _extract_via_llm(
    text: str,
    keywords: list[str],
    *,
    provider_config: dict[str, str | None] | None,
    provider_type: str,
    reasoning_effort: str | None,
) -> tuple[list[Requirement], StructuredModelResult]:
    """Return a typed requirement list and redacted provider measurement."""
    result = invoke_structured_text(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=_build_user_prompt(text, keywords),
        provider_config=provider_config,
        provider_type=provider_type,
        max_output_tokens=_MAX_REQUIREMENT_OUTPUT_TOKENS,
        temperature=0.1,
        reasoning_effort=reasoning_effort,
    )
    match = re.search(r"\[.*\]", result.content, re.DOTALL)
    if not match:
        raise ProviderInvocationError(
            "provider_response_invalid",
            "模型服务未返回可解析的需求清单，正在按策略降级处理。",
            retryable=True,
        )
    try:
        items = json.loads(match.group())
    except json.JSONDecodeError as exc:
        raise ProviderInvocationError(
            "provider_response_invalid",
            "模型服务未返回可解析的需求清单，正在按策略降级处理。",
            retryable=True,
        ) from exc
    if not isinstance(items, list):
        raise ProviderInvocationError(
            "provider_response_invalid",
            "模型服务未返回可解析的需求清单，正在按策略降级处理。",
            retryable=True,
        )
    requirements = [
        Requirement(
            section_key=str(item.get("section_key") or "extracted")[:120],
            requirement_text=str(item.get("requirement_text") or "")[:500],
            priority=str(item.get("priority") or "normal"),
        )
        for item in items
        if isinstance(item, dict) and item.get("requirement_text")
    ]
    return requirements[:50], result


def _extract_via_pattern(text: str, keywords: list[str] | None) -> list[Requirement]:
    """Deterministic fallback for a bounded requirement extraction failure."""
    pattern = re.compile(r"\b(" + "|".join(keywords or _KEYWORDS_DEFAULT) + r")\b", re.IGNORECASE)
    requirements: list[Requirement] = []
    for line in text.split("\n"):
        line = line.strip().lstrip("- •*0-9). ")
        if not line or len(line) < 10 or not pattern.search(line):
            continue
        priority = (
            "high"
            if re.search(r"\b(must|shall|mandatory|required)\b", line, re.IGNORECASE)
            else "normal"
        )
        requirements.append(
            Requirement(
                section_key="extracted",
                requirement_text=line[:500],
                priority=priority,
            )
        )
    return requirements[:50]


def _load_project_source(project_id: str) -> tuple[list[str], str]:
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        keywords = _KEYWORDS_DEFAULT
        if project and project.scenario_package:
            try:
                keywords = get_scenario_or_raise(project.scenario_package).requirement_keywords
            except ValueError:
                pass
        assets = list(
            db.scalars(
                select(ParsedAsset)
                .join(SourceDocument, ParsedAsset.source_document_id == SourceDocument.id)
                .join(Bundle, SourceDocument.bundle_id == Bundle.id)
                .where(Bundle.project_id == project_id)
            )
        )
        texts: list[str] = []
        for asset in assets:
            content = asset.content_json
            if isinstance(content, dict):
                texts.append(str(content.get("text") or json.dumps(content)))
            elif isinstance(content, str):
                texts.append(content)
        return keywords, "\n\n".join(texts)
    finally:
        db.close()


def _persist_requirements(project_id: str, requirements: list[Requirement]) -> list[Requirement]:
    """Persist requirements and return their durable ids for this workflow only."""
    db = SessionLocal()
    try:
        existing = {
            (item.section_key, item.requirement_text): item
            for item in db.scalars(
                select(RequirementItem).where(RequirementItem.project_id == project_id)
            ).all()
        }
        persisted: list[tuple[Requirement, RequirementItem]] = []
        seen: set[tuple[str, str]] = set()
        for requirement in requirements:
            identity = (requirement["section_key"], requirement["requirement_text"])
            if identity in seen:
                continue
            seen.add(identity)
            item = existing.get(identity)
            if item is None:
                item = RequirementItem(
                    project_id=project_id,
                    section_key=requirement["section_key"],
                    requirement_text=requirement["requirement_text"],
                    priority=requirement["priority"],
                    status="open",
                )
                db.add(item)
                existing[identity] = item
            persisted.append((requirement, item))
        db.flush()
        db.commit()
        return [
            Requirement(
                id=item.id,
                section_key=requirement["section_key"],
                requirement_text=requirement["requirement_text"],
                priority=requirement["priority"],
            )
            for requirement, item in persisted
        ]
    except Exception:
        db.rollback()
        logger.exception("Failed to persist extracted requirements for project %s", project_id)
        raise
    finally:
        db.close()


def rfp_parser_node(state: BidPilotState) -> dict:
    """Extract project requirements through the governed workflow model path."""
    start = time.monotonic()
    project_id: str = state["project_id"]
    section_key: str = state["section_key"]
    run_id = state.get("run_id")
    provider_config_id: str | None = state.get("provider_config_id")
    reasoning_effort: str | None = state.get("reasoning_effort")

    keywords, combined_text = _load_project_source(project_id)
    if not combined_text.strip():
        history = record_agent_call(
            agent="rfp_parser",
            action="extract_requirements",
            input_summary=f"project_id={project_id}, section={section_key}, no_text",
            output_summary="requirements[0], empty (no parsed assets)",
            duration_ms=int((time.monotonic() - start) * 1000),
            success=True,
        )
        return {"requirements": [], "requirements_parsed": True, "agent_history": history}

    requirements: list[Requirement]
    extraction_method = "pattern"
    degradation_code: str | None = None
    call_reservation_key: str | None = None
    try:
        provider_config, provider_type = resolve_structured_provider(provider_config_id)
        if isinstance(run_id, str) and run_id:
            call = begin_workflow_model_call(
                run_id=run_id,
                workload="workflow_requirement_extraction",
                operation_key="requirements-extraction",
            )
            call_reservation_key = call.reservation_key
        requirements, result = _extract_via_llm(
            combined_text,
            keywords,
            provider_config=provider_config,
            provider_type=provider_type,
            reasoning_effort=reasoning_effort,
        )
        if isinstance(run_id, str) and run_id:
            record_workflow_model_usage(
                run_id=run_id,
                provider_type=result.provider_type,
                model_name=result.model_used,
                measurement=result.usage,
                workload="workflow_requirement_extraction",
                reservation_key=call_reservation_key,
            )
        extraction_method = "llm"
    except ProviderInvocationError as exc:
        if isinstance(run_id, str) and run_id:
            resolve_workflow_model_call_failure(
                run_id=run_id,
                reservation_key=call_reservation_key,
                error_code=exc.error_code,
            )
        logger.warning("Requirement extraction degraded: code=%s", exc.error_code)
        requirements = _extract_via_pattern(combined_text, keywords)
        degradation_code = exc.error_code

    persisted_requirements = _persist_requirements(project_id, requirements)
    if persisted_requirements is not None:
        requirements = persisted_requirements
    duration_ms = int((time.monotonic() - start) * 1000)
    output = f"requirements[{len(requirements)}], method={extraction_method}"
    if degradation_code:
        output = f"{output}, degraded={degradation_code}"
    history = record_agent_call(
        agent="rfp_parser",
        action="extract_requirements",
        input_summary=(
            f"project_id={project_id}, section={section_key}, text_len={len(combined_text)}, "
            f"method={extraction_method}"
        ),
        output_summary=output,
        duration_ms=duration_ms,
        success=True,
    )
    return {
        "requirements": requirements,
        "requirements_parsed": True,
        "agent_history": history,
    }
