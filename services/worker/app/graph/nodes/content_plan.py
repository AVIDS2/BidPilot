"""Content-plan node: structure evidence into a writing plan before drafting.

OpenBidKit-style content planning happens *before* body generation:
pick evidence, outline tables/figures, and list key claims to cover.
This first slice is deterministic (no extra model call) so it stays cheap
and always available even when providers are down.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from app.db import SessionLocal
from contracts.response_plans import (
    ResponsePlanScopeError,
    capture_response_plan_binding,
    ensure_response_plan_section,
)

from ..state import BidPilotState, ContentPlan, ContentPlanItem
from ._history import record_agent_call

logger = logging.getLogger(__name__)

_MAX_KEY_POINTS = 6
_MAX_EVIDENCE_PICKS = 5
_MAX_TABLES = 3
_MAX_FIGURES = 2


def _sentence_split(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？.!?；;])\s*|\n+", text)
    return [p.strip() for p in parts if p and p.strip()]


def _looks_like_table(text: str) -> bool:
    return bool(re.search(r"\|.+\|", text) or re.search(r"(表格|表\s*\d|对比|清单)", text))


def _looks_like_figure(text: str) -> bool:
    return bool(re.search(r"(架构图|流程图|示意图|拓扑|图\s*\d|diagram|architecture)", text, re.I))


def _key_points_from_chunks(chunks: list[dict[str, Any]], limit: int = _MAX_KEY_POINTS) -> list[str]:
    points: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        content = str(chunk.get("content") or "")
        for sentence in _sentence_split(content):
            if len(sentence) < 8 or len(sentence) > 120:
                continue
            normalized = re.sub(r"\s+", " ", sentence)
            if normalized in seen:
                continue
            seen.add(normalized)
            points.append(normalized)
            if len(points) >= limit:
                return points
    return points


def build_content_plan(
    *,
    section_key: str,
    evidence_chunks: list[dict[str, Any]],
    requirements: list[dict[str, Any]] | None = None,
) -> ContentPlan:
    """Build a structured writing plan from retrieved evidence."""
    requirements = requirements or []
    evidence_picks: list[ContentPlanItem] = []
    tables: list[ContentPlanItem] = []
    figures: list[ContentPlanItem] = []

    for index, chunk in enumerate(evidence_chunks[:_MAX_EVIDENCE_PICKS], start=1):
        content = str(chunk.get("content") or "")
        chunk_id = str(chunk.get("chunk_id") or f"chunk-{index}")
        title = content[:40].replace("\n", " ").strip() or f"证据 {index}"
        evidence_picks.append(
            {
                "kind": "evidence",
                "title": title,
                "detail": content[:240],
                "source_ref": chunk_id,
            }
        )
        if _looks_like_table(content) and len(tables) < _MAX_TABLES:
            tables.append(
                {
                    "kind": "table",
                    "title": f"建议表格 {len(tables) + 1}",
                    "detail": content[:160],
                    "source_ref": chunk_id,
                }
            )
        if _looks_like_figure(content) and len(figures) < _MAX_FIGURES:
            figures.append(
                {
                    "kind": "figure",
                    "title": f"建议附图 {len(figures) + 1}",
                    "detail": content[:160],
                    "source_ref": chunk_id,
                }
            )

    # If no table/figure cues, still suggest a lightweight structure for long sections.
    if not tables and evidence_chunks:
        tables.append(
            {
                "kind": "table",
                "title": "要点对照表",
                "detail": "将关键能力、交付物、验收标准整理为对照表。",
                "source_ref": None,
            }
        )

    req_points = [
        str(item.get("requirement_text") or "").strip()
        for item in requirements
        if isinstance(item, dict) and str(item.get("requirement_text") or "").strip()
    ][:4]
    key_points = req_points + _key_points_from_chunks(evidence_chunks)
    # Deduplicate key points.
    deduped: list[str] = []
    seen_pts: set[str] = set()
    for point in key_points:
        if point in seen_pts:
            continue
        seen_pts.add(point)
        deduped.append(point)
        if len(deduped) >= _MAX_KEY_POINTS:
            break

    outline = [
        f"1. 开篇：明确 {section_key} 的目标与范围",
        "2. 主体：按证据要点展开，必要时插入对照表",
        "3. 收束：交付物、风险与后续安排",
    ]
    if figures:
        outline.insert(2, "3. 附图：补充架构/流程示意（引用证据）")
        outline[3] = "4. 收束：交付物、风险与后续安排"

    summary = (
        f"章节 {section_key}：选用 {len(evidence_picks)} 条证据、"
        f"{len(tables)} 个表格建议、{len(figures)} 个附图建议、"
        f"{len(deduped)} 个写作要点。"
    )
    return {
        "section_key": section_key,
        "summary": summary,
        "outline": outline,
        "key_points": deduped,
        "evidence_picks": evidence_picks,
        "tables": tables,
        "figures": figures,
        "gaps": (
            ["未检索到可用证据，草稿将标注证据缺口。"]
            if not evidence_chunks
            else []
        ),
    }


def _response_plan_failure(
    *,
    started_at: float,
    section_key: str,
    error_code: str,
) -> dict:
    history = record_agent_call(
        agent="content_plan",
        action="plan_section_content",
        input_summary=f"section={section_key}, durable_response_plan=unavailable",
        output_summary=f"ERROR: {error_code}",
        duration_ms=int((time.monotonic() - started_at) * 1000),
        success=False,
        error=error_code,
    )
    return {
        "content_plan": None,
        "content_plan_ready": False,
        "error": "content_plan: 响应计划快照不可用，请重新发起工作流。",
        "agent_history": history,
    }


def content_plan_node(state: BidPilotState) -> dict:
    """LangGraph node: produce a deterministic content plan after retrieval."""
    start = time.monotonic()
    section_key: str = state["section_key"]
    evidence_chunks = list(state.get("evidence_chunks") or [])
    requirements = list(state.get("requirements") or [])
    response_plan_update: dict[str, object] = {}

    evidence_set_id = state.get("evidence_set_id")
    run_id = state.get("run_id")
    if isinstance(evidence_set_id, str) and evidence_set_id:
        if not isinstance(run_id, str) or not run_id:
            return _response_plan_failure(
                started_at=start,
                section_key=section_key,
                error_code="response_plan_execution_run_required",
            )
        db = SessionLocal()
        try:
            plan_section = ensure_response_plan_section(
                db,
                project_id=state["project_id"],
                section_key=section_key,
                deliverable_section_id=state.get("deliverable_section_id"),
            )
            # Only durable requirement assignments are allowed to shape the
            # model-facing plan. Graph state is not the business source of truth.
            requirements = list(plan_section.requirements)
            plan = build_content_plan(
                section_key=section_key,
                evidence_chunks=evidence_chunks,
                requirements=requirements,
            )
            if plan_section.unmapped_requirement_ids:
                plan["gaps"] = [
                    *plan["gaps"],
                    (
                        f"有 {len(plan_section.unmapped_requirement_ids)} 条需求尚未分配章节，"
                        "需人工完成章节映射。"
                    ),
                ]
            raw_iteration = state.get("iteration", 0)
            generation_iteration = raw_iteration + 1 if isinstance(raw_iteration, int) else 1
            binding = capture_response_plan_binding(
                db,
                project_id=state["project_id"],
                execution_run_id=run_id,
                evidence_set_id=evidence_set_id,
                response_plan_section_id=plan_section.response_plan_section_id,
                generation_iteration=max(generation_iteration, 1),
                content_plan=plan,
            )
            db.commit()
            plan = binding.content_plan
            response_plan_update = {
                "response_plan_id": binding.response_plan_id,
                "response_plan_section_id": binding.response_plan_section_id,
                "response_plan_evidence_binding_id": (
                    binding.response_plan_evidence_binding_id
                ),
                "response_plan_version": binding.response_plan_version,
            }
        except ResponsePlanScopeError as exc:
            db.rollback()
            return _response_plan_failure(
                started_at=start,
                section_key=section_key,
                error_code=str(exc),
            )
        except Exception:
            db.rollback()
            logger.exception("Unable to persist response plan for section %s", section_key)
            return _response_plan_failure(
                started_at=start,
                section_key=section_key,
                error_code="response_plan_persistence_failed",
            )
        finally:
            db.close()
    else:
        # This compatibility path keeps deterministic unit-node tests pure.
        # Product graph executions always arrive with an EvidenceSet.
        plan = build_content_plan(
            section_key=section_key,
            evidence_chunks=evidence_chunks,
            requirements=requirements,
        )
    duration_ms = int((time.monotonic() - start) * 1000)
    history = record_agent_call(
        agent="content_plan",
        action="plan_section_content",
        input_summary=(
            f"section={section_key}, evidence={len(evidence_chunks)}, "
            f"requirements={len(requirements)}"
        ),
        output_summary=(
            f"outline={len(plan['outline'])}, key_points={len(plan['key_points'])}, "
            f"tables={len(plan['tables'])}, figures={len(plan['figures'])}, "
            f"gaps={len(plan['gaps'])}"
        ),
        duration_ms=duration_ms,
        success=True,
    )
    logger.info(
        "Content plan for %s: evidence=%d key_points=%d",
        section_key,
        len(evidence_chunks),
        len(plan["key_points"]),
    )
    # Re-planning after review/HITL rejection must invalidate the prior draft so
    # the graph cannot skip drafting or re-enter quality review on stale output.
    replan = bool(state.get("draft_created") or state.get("review_result") is not None)
    update: dict = {
        "content_plan": plan,
        "content_plan_ready": True,
        "agent_history": history,
        **response_plan_update,
    }
    if replan:
        update.update(
            {
                "draft_created": False,
                "draft_markdown": "",
                "draft_model_used": "",
                "review_result": None,
                "review_passed": False,
                "review_status": "not_started",
                "review_degradation_code": None,
                "claim_candidates": [],
                "claim_integrity_status": "not_assessed",
                # Consume the rejection so a later supervisor pass does not loop.
                "human_decision": None,
            }
        )
    return update
