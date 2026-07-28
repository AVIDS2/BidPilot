"""Persist result node: write draft, section version, and evidence to DB.

Single DB transaction that:
1. Looks up or creates the DeliverableSection for the section_key.
2. Creates a new SectionVersion with the draft content.
3. Creates Evidence records with validated source locators.
4. Updates the ExecutionRun status to "succeeded".
"""

from __future__ import annotations

import logging
import re
import time
from datetime import UTC, datetime

from app.db import SessionLocal
from app.models import (
    AuditEvent,
    Deliverable,
    DeliverableSection,
    Evidence,
    ExecutionRun,
    Claim,
    ClaimEvidenceLink,
    RequirementClaimLink,
    RequirementEvidenceLink,
    RequirementItem,
    ReviewThread,
    SectionVersion,
)
from app.retrieval.evidence_sets import EvidenceSetScopeError, load_authorized_evidence_set
from contracts.response_plans import (
    ResponsePlanBindingSnapshot,
    ResponsePlanScopeError,
    load_authorized_response_plan_binding,
)
from sqlalchemy import func, select

from ..state import BidPilotState
from ._history import record_agent_call

logger = logging.getLogger(__name__)


def _find_or_create_section(
    db,
    project_id: str,
    section_key: str,
) -> DeliverableSection:
    """Find existing DeliverableSection or create one under the project's deliverable.

    If no Deliverable exists for the project yet, creates one automatically.
    """
    section = db.scalar(
        select(DeliverableSection)
        .join(Deliverable, Deliverable.id == DeliverableSection.deliverable_id)
        .where(
            Deliverable.project_id == project_id,
            DeliverableSection.section_key == section_key,
        )
        .limit(1)
    )
    if section is not None:
        return section

    # Find or create deliverable for this project
    deliverable = db.scalar(
        select(Deliverable).where(Deliverable.project_id == project_id).limit(1)
    )
    if deliverable is None:
        deliverable = Deliverable(
            project_id=project_id,
            type="proposal",
            title=f"Deliverable for {section_key}",
            status="draft",
        )
        db.add(deliverable)
        db.flush()

    # Append after existing outline chapters so sort_order stays contiguous.
    next_order = db.scalar(
        select(func.max(DeliverableSection.sort_order)).where(
            DeliverableSection.deliverable_id == deliverable.id
        )
    )
    section = DeliverableSection(
        deliverable_id=deliverable.id,
        section_key=section_key,
        title=section_key.replace("-", " ").title(),
        status="draft",
        assignee_type="ai",
        sort_order=int(next_order or 0) + 1,
    )
    db.add(section)
    db.flush()
    return section


def _next_version_number(db, section_id: str) -> int:
    """Determine the next version number for a section."""
    existing = db.scalar(
        select(SectionVersion)
        .where(SectionVersion.deliverable_section_id == section_id)
        .order_by(SectionVersion.version_number.desc())
        .limit(1)
    )
    return (existing.version_number + 1) if existing else 1


def _find_existing_version_for_run(
    db,
    *,
    project_id: str,
    section_key: str,
    run_id: str,
    iteration: int,
) -> SectionVersion | None:
    """Return a prior candidate for the same durable graph iteration."""
    return db.scalar(
        select(SectionVersion)
        .join(DeliverableSection, DeliverableSection.id == SectionVersion.deliverable_section_id)
        .join(Deliverable, Deliverable.id == DeliverableSection.deliverable_id)
        .where(
            Deliverable.project_id == project_id,
            DeliverableSection.section_key == section_key,
            SectionVersion.generation_run_id == run_id,
            SectionVersion.generation_iteration == iteration,
        )
        .limit(1)
    )


def _normalize_claim_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _recompute_deliverable_approval(db, deliverable: Deliverable) -> None:
    """Approve a deliverable when every non-empty section is approved.

    Empty outline placeholders may remain draft (OpenBidKit-style partial export).
    A section is non-empty when it has at least one SectionVersion.
    """
    sections = list(
        db.scalars(
            select(DeliverableSection).where(DeliverableSection.deliverable_id == deliverable.id)
        ).all()
    )
    if not sections:
        return

    non_empty: list[DeliverableSection] = []
    for section in sections:
        has_version = db.scalar(
            select(SectionVersion.id)
            .where(SectionVersion.deliverable_section_id == section.id)
            .limit(1)
        )
        if has_version is not None:
            non_empty.append(section)

    if non_empty and all(
        section.status == "approved" and section.approved_version_id is not None
        for section in non_empty
    ):
        deliverable.status = "approved"
    elif any(
        section.approved_version_id is not None or section.status == "in_review"
        for section in non_empty
    ):
        # Partial progress: keep draft/in_review, export still allowed via approved sections.
        deliverable.status = "in_review"
    else:
        deliverable.status = "draft"


def _review_thread_for_version(db, section_version_id: str) -> ReviewThread | None:
    return db.scalar(
        select(ReviewThread)
        .where(ReviewThread.section_version_id == section_version_id)
        .order_by(ReviewThread.id.desc())
        .limit(1)
    )


def _load_authorized_evidence_for_persistence(
    db,
    *,
    state: BidPilotState,
    project_id: str,
) -> tuple[list[dict], str, dict]:
    """Use only the durable, scope-checked evidence snapshot at write time."""
    evidence_set_id = state.get("evidence_set_id")
    if not isinstance(evidence_set_id, str) or not evidence_set_id:
        raise EvidenceSetScopeError("evidence_set_required_for_persistence")

    snapshot = load_authorized_evidence_set(
        db,
        evidence_set_id=evidence_set_id,
        project_id=project_id,
        execution_run_id=state["run_id"],
    )
    if snapshot.status == "invalidated":
        raise EvidenceSetScopeError("evidence_set_invalidated_before_persistence")

    return (
        snapshot.evidence_chunks,
        snapshot.id,
        {
            "evidence_set_id": snapshot.id,
            "evidence_set_status": snapshot.status,
            "evidence_set_unmet_requirement_ids": list(snapshot.unmet_requirement_ids),
            "evidence_set_degraded_reasons": list(
                dict.fromkeys([*snapshot.degraded_reasons, *snapshot.rejected_reasons])
            ),
            "_evidence_set_items": snapshot.items,
        },
    )


def _load_authorized_response_plan_for_persistence(
    db,
    *,
    state: BidPilotState,
    project_id: str,
    evidence_set_id: str,
) -> ResponsePlanBindingSnapshot:
    """Require the same plan/evidence binding that shaped the model draft."""
    binding_id = state.get("response_plan_evidence_binding_id")
    if not isinstance(binding_id, str) or not binding_id:
        raise ResponsePlanScopeError("response_plan_binding_required_for_persistence")
    snapshot = load_authorized_response_plan_binding(
        db,
        response_plan_evidence_binding_id=binding_id,
        project_id=project_id,
        execution_run_id=state["run_id"],
        section_key=state["section_key"],
    )
    if snapshot.evidence_set_id != evidence_set_id:
        raise ResponsePlanScopeError("response_plan_binding_evidence_mismatch")
    iteration = state.get("iteration")
    if isinstance(iteration, int) and iteration > 0 and snapshot.generation_iteration != iteration:
        raise ResponsePlanScopeError("response_plan_binding_iteration_mismatch")
    return snapshot


def _public_persist_failure(exc: BaseException) -> tuple[str, str]:
    """Translate persistence failures before they reach durable run state."""
    if isinstance(exc, EvidenceSetScopeError):
        return (
            "evidence_set_unavailable",
            "本次证据集已不可用，请重新发起工作流。",
        )
    if isinstance(exc, ResponsePlanScopeError):
        return (
            "response_plan_unavailable",
            "本次响应计划已不可用，请重新发起工作流。",
        )
    return (
        "persistence_failed",
        "草稿结果未能保存，请检查项目状态后重试。",
    )


def _ensure_open_review_thread(
    db,
    *,
    project_id: str,
    section: DeliverableSection,
    version: SectionVersion,
    run_id: str,
) -> ReviewThread:
    """Bind one durable human-review thread to an immutable candidate."""
    thread = _review_thread_for_version(db, version.id)
    if thread is not None:
        return thread

    thread = ReviewThread(
        deliverable_section_id=section.id,
        section_version_id=version.id,
        status="open",
        opened_by=run_id,
    )
    db.add(thread)
    db.flush()
    db.add(
        AuditEvent(
            project_id=project_id,
            actor_type="workflow",
            actor_id=run_id,
            event_type="review.requested",
            payload_json={
                "section_id": section.id,
                "section_key": section.section_key,
                "section_version_id": version.id,
                "version_number": version.version_number,
            },
        )
    )
    return thread


def _unique_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    values: list[str] = []
    for item in value:
        if isinstance(item, str) and item and item not in values:
            values.append(item)
    return values


def _persist_claim_candidates(
    db,
    *,
    project_id: str,
    section_key: str,
    section_version_id: str,
    run_id: str,
    draft_markdown: str,
    candidates: list[dict],
    evidence_id_by_chunk_id: dict[str, str],
    authorized_requirement_ids: set[str] | None = None,
) -> int:
    """Persist only server-validated proposal claims for this section version."""
    valid_requirement_ids = (
        authorized_requirement_ids
        if authorized_requirement_ids is not None
        else set(
            db.scalars(
                select(RequirementItem.id).where(
                    RequirementItem.project_id == project_id,
                    RequirementItem.section_key.in_((section_key, "extracted")),
                )
            ).all()
        )
    )
    existing_claims = {
        (_normalize_claim_text(claim.claim_text), claim.claim_type): claim
        for claim in db.scalars(
            select(Claim).where(
                Claim.project_id == project_id,
                Claim.section_version_id == section_version_id,
            )
        ).all()
    }
    existing_requirement_evidence_pairs = set(
        db.execute(
            select(
                RequirementEvidenceLink.requirement_id,
                RequirementEvidenceLink.evidence_id,
            )
            .join(RequirementItem, RequirementItem.id == RequirementEvidenceLink.requirement_id)
            .where(
                RequirementItem.project_id == project_id,
                RequirementEvidenceLink.relation_type == "supports",
            )
        ).all()
    )
    normalized_draft = _normalize_claim_text(draft_markdown)
    created_count = 0
    for candidate in candidates:
        claim_text = candidate.get("claim_text")
        claim_type = candidate.get("claim_type")
        if (
            not isinstance(claim_text, str)
            or not isinstance(claim_type, str)
            or claim_type not in {"factual", "inference"}
        ):
            continue
        claim_text = claim_text.strip()
        normalized_claim = _normalize_claim_text(claim_text)
        requirement_ids = _unique_strings(candidate.get("requirement_ids"))
        evidence_chunk_ids = _unique_strings(candidate.get("evidence_chunk_ids"))
        if (
            not normalized_claim
            or normalized_claim not in normalized_draft
            or not requirement_ids
            or not evidence_chunk_ids
            or not set(requirement_ids).issubset(valid_requirement_ids)
            or not set(evidence_chunk_ids).issubset(evidence_id_by_chunk_id)
        ):
            continue

        key = (normalized_claim, claim_type)
        claim = existing_claims.get(key)
        if claim is None:
            claim = Claim(
                project_id=project_id,
                claim_text=claim_text,
                claim_type=claim_type,
                status="draft",
                section_version_id=section_version_id,
                generation_run_id=run_id,
                created_by_actor="ai",
            )
            db.add(claim)
            db.flush()
            existing_claims[key] = claim
            created_count += 1

        linked_requirement_ids = {link.requirement_id for link in claim.requirement_links}
        for requirement_id in requirement_ids:
            if requirement_id not in linked_requirement_ids:
                claim.requirement_links.append(
                    RequirementClaimLink(requirement_id=requirement_id, coverage_role="direct")
                )
        linked_evidence_ids = {link.evidence_id for link in claim.evidence_links}
        for chunk_id in evidence_chunk_ids:
            evidence_id = evidence_id_by_chunk_id[chunk_id]
            if evidence_id not in linked_evidence_ids:
                claim.evidence_links.append(
                    ClaimEvidenceLink(
                        evidence_id=evidence_id,
                        relation_type="supports",
                        verification_status="unverified",
                    )
                )
            for requirement_id in requirement_ids:
                pair = (requirement_id, evidence_id)
                if pair not in existing_requirement_evidence_pairs:
                    db.add(
                        RequirementEvidenceLink(
                            requirement_id=requirement_id,
                            evidence_id=evidence_id,
                            relation_type="supports",
                            verification_status="unverified",
                        )
                    )
                    existing_requirement_evidence_pairs.add(pair)
    return created_count


def persist_result_node(state: BidPilotState) -> dict:
    """LangGraph node: persist the final draft and evidence to the database.

    Creates a SectionVersion with the draft markdown, links each evidence
    chunk as an Evidence record with its validated source locator, and marks
    the ExecutionRun as succeeded. Retrieval rank is intentionally not stored
    as an evidence-confidence value.

    If no evidence chunks were retrieved, adds a missing-evidence marker.

    Returns:
        Partial state update with ``section_version_id``,
        ``persisted`` flag, and ``agent_history`` record.
    """
    start = time.monotonic()
    project_id: str = state["project_id"]
    section_key: str = state["section_key"]
    run_id: str = state["run_id"]
    draft_markdown: str = state.get("draft_markdown", "")
    draft_model_used: str = state.get("draft_model_used", "")
    evidence_chunks: list[dict] = []
    evidence_set_id: str | None = None
    evidence_set_items: tuple = ()
    evidence_state_update: dict = {}
    response_plan_state_update: dict = {}
    claim_candidates = state.get("claim_candidates", [])
    claim_integrity_status = str(state.get("claim_integrity_status") or "not_assessed")
    iteration: int = state.get("iteration", 0)

    db = SessionLocal()
    try:
        evidence_chunks, evidence_set_id, evidence_state_update = (
            _load_authorized_evidence_for_persistence(
                db,
                state=state,
                project_id=project_id,
            )
        )
        evidence_set_items = tuple(evidence_state_update.pop("_evidence_set_items", ()))
        response_plan_binding = _load_authorized_response_plan_for_persistence(
            db,
            state=state,
            project_id=project_id,
            evidence_set_id=evidence_set_id,
        )
        response_plan_state_update = {
            "response_plan_id": response_plan_binding.response_plan_id,
            "response_plan_section_id": response_plan_binding.response_plan_section_id,
            "response_plan_evidence_binding_id": (
                response_plan_binding.response_plan_evidence_binding_id
            ),
            "response_plan_version": response_plan_binding.response_plan_version,
        }
        human_decision = state.get("human_decision")
        requires_human_review = bool(state.get("review_passed")) and human_decision is None
        existing_version = _find_existing_version_for_run(
            db,
            project_id=project_id,
            section_key=section_key,
            run_id=run_id,
            iteration=iteration,
        )
        if existing_version is not None:
            claim_count = len(
                list(
                    db.scalars(
                        select(Claim.id).where(Claim.section_version_id == existing_version.id)
                    ).all()
                )
            )
            section = _find_or_create_section(db, project_id, section_key)
            if section.id != response_plan_binding.deliverable_section_id:
                raise ResponsePlanScopeError("response_plan_binding_deliverable_section_mismatch")
            if (
                existing_version.response_plan_section_id
                != response_plan_binding.response_plan_section_id
                or existing_version.response_plan_evidence_binding_id
                != response_plan_binding.response_plan_evidence_binding_id
            ):
                raise ResponsePlanScopeError("section_version_response_plan_binding_mismatch")
            deliverable = db.get(Deliverable, section.deliverable_id)
            run = db.get(ExecutionRun, run_id)
            if requires_human_review:
                # Celery may replay before the API observes the graph pause. Keep
                # the candidate and its review thread stable instead of making a
                # second SectionVersion.
                section.status = "in_review"
                _ensure_open_review_thread(
                    db,
                    project_id=project_id,
                    section=section,
                    version=existing_version,
                    run_id=run_id,
                )
                if deliverable is not None:
                    _recompute_deliverable_approval(db, deliverable)
                if run is not None:
                    run.status = "awaiting_human"
                    run.finished_at = None
                    run.output_json = {
                        **(run.output_json or {}),
                        "section_key": section_key,
                        "response_plan_id": response_plan_binding.response_plan_id,
                        "response_plan_version": response_plan_binding.response_plan_version,
                        "response_plan_section_id": response_plan_binding.response_plan_section_id,
                        "response_plan_evidence_binding_id": (
                            response_plan_binding.response_plan_evidence_binding_id
                        ),
                        "section_version_id": existing_version.id,
                        "iterations": iteration,
                        "section_status": section.status,
                        "awaiting_human": True,
                    }
                db.commit()
            elif human_decision == "approved":
                section.status = "approved"
                section.approved_version_id = existing_version.id
                if deliverable is not None:
                    _recompute_deliverable_approval(db, deliverable)
                thread = _review_thread_for_version(db, existing_version.id)
                if thread is not None:
                    thread.status = "approved"
                if run is not None:
                    run.status = "succeeded"
                    run.finished_at = datetime.now(UTC)
                    run.output_json = {
                        **(run.output_json or {}),
                        "section_key": section_key,
                        "response_plan_id": response_plan_binding.response_plan_id,
                        "response_plan_version": response_plan_binding.response_plan_version,
                        "response_plan_section_id": response_plan_binding.response_plan_section_id,
                        "response_plan_evidence_binding_id": (
                            response_plan_binding.response_plan_evidence_binding_id
                        ),
                        "section_version_id": existing_version.id,
                        "iterations": iteration,
                        "section_status": section.status,
                        "human_decision": human_decision,
                    }
                db.commit()
            # Reload can mark a persisted evidence set degraded/invalidated;
            # retain that status even when this delivery is an idempotent replay.
            db.commit()
            history = record_agent_call(
                agent="persist_result",
                action="persist_to_db",
                input_summary=f"section={section_key}, run_id={run_id}, replayed=True",
                output_summary=(
                    f"section_version_id={existing_version.id}, persisted=True, "
                    f"replayed=True, claims={claim_count}, section_status={section.status}"
                ),
                duration_ms=int((time.monotonic() - start) * 1000),
                success=True,
            )
            return {
                **evidence_state_update,
                **response_plan_state_update,
                "evidence_chunks": evidence_chunks,
                "section_version_id": existing_version.id,
                "persisted": True,
                "claim_count": claim_count,
                "claim_integrity_status": claim_integrity_status,
                "agent_history": history,
            }

        # 1. Find or create the deliverable section
        section = _find_or_create_section(db, project_id, section_key)
        if section.id != response_plan_binding.deliverable_section_id:
            raise ResponsePlanScopeError("response_plan_binding_deliverable_section_mismatch")

        # 2. Create section version. A new candidate cannot inherit a prior
        # approval; the old approved pointer remains a stable export snapshot.
        section.status = "draft"
        next_ver = _next_version_number(db, section.id)
        sv = SectionVersion(
            deliverable_section_id=section.id,
            version_number=next_ver,
            content_markdown=draft_markdown,
            created_by_actor="ai",
            generation_run_id=run_id,
            generation_iteration=iteration,
            evidence_set_id=evidence_set_id,
            response_plan_section_id=response_plan_binding.response_plan_section_id,
            response_plan_evidence_binding_id=(
                response_plan_binding.response_plan_evidence_binding_id
            ),
        )
        db.add(sv)
        db.flush()
        section_version_id: str = sv.id

        # 3. Persist validated locators. Retrieval ranking is not a calibrated
        # evidence-confidence score, so confidence remains unset here.
        evidence_id_by_chunk_id: dict[str, str] = {}
        if evidence_set_items:
            evidence_rows: list[tuple[str, Evidence]] = []
            seen_chunk_ids: set[str] = set()
            for item in evidence_set_items:
                chunk_id = item.chunk_id
                if chunk_id in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(chunk_id)
                ev = Evidence(
                    project_id=project_id,
                    section_version_id=section_version_id,
                    evidence_set_item_id=item.id,
                    source_document_id=item.source_document_id,
                    chunk_id=chunk_id,
                    quote_text=item.quote_text[:500],
                    locator_json=dict(item.locator_json),
                    confidence=None,
                )
                db.add(ev)
                evidence_rows.append((chunk_id, ev))
            db.flush()
            evidence_id_by_chunk_id = {
                chunk_id: evidence.id
                for chunk_id, evidence in evidence_rows
            }
        else:
            # Mark that no evidence was available
            ev = Evidence(
                project_id=project_id,
                section_version_id=section_version_id,
                quote_text=(
                    "[NO EVIDENCE FOUND] No relevant knowledge chunks were "
                    "retrieved for this section."
                ),
                locator_json={"marker": "missing-evidence"},
                confidence=0.0,
            )
            db.add(ev)

        persisted_claim_count = _persist_claim_candidates(
            db,
            project_id=project_id,
            section_key=section_key,
            section_version_id=section_version_id,
            run_id=run_id,
            draft_markdown=draft_markdown,
            candidates=claim_candidates if isinstance(claim_candidates, list) else [],
            evidence_id_by_chunk_id=evidence_id_by_chunk_id,
            authorized_requirement_ids={
                str(requirement["id"])
                for requirement in response_plan_binding.requirements
                if isinstance(requirement.get("id"), str)
            },
        )
        if claim_integrity_status == "proposed" and not persisted_claim_count:
            claim_integrity_status = "invalid_candidates"

        # 4. A quality-passed candidate is durable before LangGraph interrupts.
        # Export remains pinned to approved_version_id until a human approves it.
        deliverable = db.get(Deliverable, section.deliverable_id)
        if requires_human_review:
            section.status = "in_review"
            _ensure_open_review_thread(
                db,
                project_id=project_id,
                section=section,
                version=sv,
                run_id=run_id,
            )
        elif human_decision == "approved":
            section.status = "approved"
            section.approved_version_id = section_version_id
        elif human_decision == "rejected_with_feedback":
            # A rejected candidate must not erase an earlier approved snapshot.
            section.status = "approved" if section.approved_version_id else "rejected"
        elif section.status in {None, "", "draft"}:
            section.status = "draft"
        if deliverable is not None:
            _recompute_deliverable_approval(db, deliverable)

        # 5. Update execution run status
        run = db.get(ExecutionRun, run_id)
        if run is not None:
            run.status = "awaiting_human" if requires_human_review else "succeeded"
            run.finished_at = None if requires_human_review else datetime.now(UTC)
            run.output_json = {
                "section_key": section_key,
                "model_used": draft_model_used,
                "evidence_count": len(evidence_chunks),
                "evidence_set_id": evidence_set_id,
                "evidence_set_status": evidence_state_update.get("evidence_set_status"),
                "evidence_set_unmet_requirement_count": len(
                    evidence_state_update.get("evidence_set_unmet_requirement_ids", [])
                ),
                "response_plan_id": response_plan_binding.response_plan_id,
                "response_plan_version": response_plan_binding.response_plan_version,
                "response_plan_section_id": response_plan_binding.response_plan_section_id,
                "response_plan_evidence_binding_id": (
                    response_plan_binding.response_plan_evidence_binding_id
                ),
                "section_version_id": section_version_id,
                "iterations": iteration,
                "claim_integrity_status": claim_integrity_status,
                "claim_candidate_count": len(claim_candidates),
                "claim_count": persisted_claim_count,
                "section_status": section.status,
                "human_decision": human_decision,
                "awaiting_human": requires_human_review,
            }

        db.commit()

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "Persisted section %s version %d (run=%s, evidence=%d, claims=%d)",
            section_key,
            next_ver,
            run_id,
            len(evidence_chunks),
            persisted_claim_count,
        )

        history = record_agent_call(
            agent="persist_result",
            action="persist_to_db",
            input_summary=(
                f"section={section_key}, run_id={run_id}, "
                f"draft_len={len(draft_markdown)}, evidence={len(evidence_chunks)}, "
                f"claims={persisted_claim_count}, iteration={iteration}"
            ),
            output_summary=(
                f"section_version_id={section_version_id}, "
                f"version_number={next_ver}, persisted=True, claims={persisted_claim_count}, "
                f"integrity={claim_integrity_status}"
            ),
            duration_ms=duration_ms,
            success=True,
        )

        return {
            **evidence_state_update,
            **response_plan_state_update,
            "evidence_chunks": evidence_chunks,
            "section_version_id": section_version_id,
            "persisted": True,
            "claim_count": persisted_claim_count,
            "claim_integrity_status": claim_integrity_status,
            "agent_history": history,
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        error_code, public_message = _public_persist_failure(exc)
        logger.exception("persist_result_node failed for run %s", run_id)
        db.rollback()

        # Try to mark the run as failed
        try:
            db2 = SessionLocal()
            run = db2.get(ExecutionRun, run_id)
            if run is not None:
                run.status = "failed"
                run.finished_at = datetime.now(UTC)
                run.output_json = {"error_code": error_code}
                db2.commit()
            db2.close()
        except Exception:
            logger.error("Also failed to update run status to failed")

        history = record_agent_call(
            agent="persist_result",
            action="persist_to_db",
            input_summary=(
                f"section={section_key}, run_id={run_id}, "
                f"draft_len={len(draft_markdown)}, evidence={len(evidence_chunks)}"
            ),
            output_summary=f"ERROR: {error_code}",
            duration_ms=duration_ms,
            success=False,
            error=error_code,
        )

        return {
            "section_version_id": None,
            "persisted": False,
            "error": f"persist_result: {public_message}",
            "agent_history": history,
        }
    finally:
        db.close()
