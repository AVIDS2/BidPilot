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
    Deliverable,
    DeliverableSection,
    Evidence,
    ExecutionRun,
    Claim,
    ClaimEvidenceLink,
    RequirementClaimLink,
    RequirementEvidenceLink,
    RequirementItem,
    SectionVersion,
)
from sqlalchemy import select

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

    section = DeliverableSection(
        deliverable_id=deliverable.id,
        section_key=section_key,
        title=section_key.replace("-", " ").title(),
        status="draft",
        assignee_type="ai",
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
) -> SectionVersion | None:
    """Return a previously committed version when a Worker delivery replays."""
    return db.scalar(
        select(SectionVersion)
        .join(DeliverableSection, DeliverableSection.id == SectionVersion.deliverable_section_id)
        .join(Deliverable, Deliverable.id == DeliverableSection.deliverable_id)
        .where(
            Deliverable.project_id == project_id,
            DeliverableSection.section_key == section_key,
            SectionVersion.generation_run_id == run_id,
        )
        .limit(1)
    )


def _normalize_claim_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


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
) -> int:
    """Persist only server-validated proposal claims for this section version."""
    valid_requirement_ids = set(
        db.scalars(
            select(RequirementItem.id).where(
                RequirementItem.project_id == project_id,
                RequirementItem.section_key.in_((section_key, "extracted")),
            )
        ).all()
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
    evidence_chunks = state.get("evidence_chunks", [])
    claim_candidates = state.get("claim_candidates", [])
    claim_integrity_status = str(state.get("claim_integrity_status") or "not_assessed")
    iteration: int = state.get("iteration", 0)

    db = SessionLocal()
    try:
        existing_version = _find_existing_version_for_run(
            db,
            project_id=project_id,
            section_key=section_key,
            run_id=run_id,
        )
        if existing_version is not None:
            claim_count = len(
                list(
                    db.scalars(
                        select(Claim.id).where(Claim.section_version_id == existing_version.id)
                    ).all()
                )
            )
            history = record_agent_call(
                agent="persist_result",
                action="persist_to_db",
                input_summary=f"section={section_key}, run_id={run_id}, replayed=True",
                output_summary=(
                    f"section_version_id={existing_version.id}, persisted=True, "
                    f"replayed=True, claims={claim_count}"
                ),
                duration_ms=int((time.monotonic() - start) * 1000),
                success=True,
            )
            return {
                "section_version_id": existing_version.id,
                "persisted": True,
                "claim_count": claim_count,
                "claim_integrity_status": claim_integrity_status,
                "agent_history": history,
            }

        # 1. Find or create the deliverable section
        section = _find_or_create_section(db, project_id, section_key)

        # 2. Create section version
        next_ver = _next_version_number(db, section.id)
        sv = SectionVersion(
            deliverable_section_id=section.id,
            version_number=next_ver,
            content_markdown=draft_markdown,
            created_by_actor="ai",
            generation_run_id=run_id,
        )
        db.add(sv)
        db.flush()
        section_version_id: str = sv.id

        # 3. Persist validated locators. Retrieval ranking is not a calibrated
        # evidence-confidence score, so confidence remains unset here.
        evidence_id_by_chunk_id: dict[str, str] = {}
        if evidence_chunks:
            evidence_rows: list[tuple[str, Evidence]] = []
            seen_chunk_ids: set[str] = set()
            for chunk in evidence_chunks:
                chunk_id = chunk.get("chunk_id")
                if isinstance(chunk_id, str) and chunk_id in seen_chunk_ids:
                    continue
                if isinstance(chunk_id, str):
                    seen_chunk_ids.add(chunk_id)
                ev = Evidence(
                    project_id=project_id,
                    section_version_id=section_version_id,
                    source_document_id=chunk.get("source_document_id"),
                    chunk_id=chunk.get("chunk_id"),
                    quote_text=chunk.get("content", "")[:500],
                    locator_json=chunk.get("locator_json") or {
                        "chunk_index": chunk.get("chunk_index")
                    },
                    confidence=None,
                )
                db.add(ev)
                if isinstance(chunk_id, str) and chunk_id:
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
        )
        if claim_integrity_status == "proposed" and not persisted_claim_count:
            claim_integrity_status = "invalid_candidates"

        # 4. Update execution run status
        run = db.get(ExecutionRun, run_id)
        if run is not None:
            run.status = "succeeded"
            run.finished_at = datetime.now(UTC)
            run.output_json = {
                "section_key": section_key,
                "model_used": draft_model_used,
                "evidence_count": len(evidence_chunks),
                "section_version_id": section_version_id,
                "iterations": iteration,
                "claim_integrity_status": claim_integrity_status,
                "claim_candidate_count": len(claim_candidates),
                "claim_count": persisted_claim_count,
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
            "section_version_id": section_version_id,
            "persisted": True,
            "claim_count": persisted_claim_count,
            "claim_integrity_status": claim_integrity_status,
            "agent_history": history,
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.exception("persist_result_node failed for run %s", run_id)
        db.rollback()

        # Try to mark the run as failed
        try:
            db2 = SessionLocal()
            run = db2.get(ExecutionRun, run_id)
            if run is not None:
                run.status = "failed"
                run.finished_at = datetime.now(UTC)
                run.output_json = {"error": str(exc)}
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
            output_summary=f"ERROR: {exc}",
            duration_ms=duration_ms,
            success=False,
            error=str(exc),
        )

        return {
            "section_version_id": None,
            "persisted": False,
            "error": f"persist_result: {exc}",
            "agent_history": history,
        }
    finally:
        db.close()
