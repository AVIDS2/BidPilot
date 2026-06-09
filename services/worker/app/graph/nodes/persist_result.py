"""Persist result node: write draft, section version, and evidence to DB.

Single DB transaction that:
1. Looks up or creates the DeliverableSection for the section_key.
2. Creates a new SectionVersion with the draft content.
3. Creates Evidence records with real cosine_distance confidence values.
4. Updates the ExecutionRun status to "succeeded".
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from app.db import SessionLocal
from app.models import (
    Deliverable,
    DeliverableSection,
    Evidence,
    ExecutionRun,
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
        select(DeliverableSection).where(
            DeliverableSection.section_key == section_key
        ).limit(1)
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


def persist_result_node(state: BidPilotState) -> dict:
    """LangGraph node: persist the final draft and evidence to the database.

    Creates a SectionVersion with the draft markdown, links each evidence
    chunk as an Evidence record with its actual cosine_distance as
    confidence, and marks the ExecutionRun as succeeded.

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
    iteration: int = state.get("iteration", 0)

    db = SessionLocal()
    try:
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

        # 3. Create evidence records with real cosine_distance as confidence
        if evidence_chunks:
            for chunk in evidence_chunks:
                # cosine_distance: 0 = identical, 1 = opposite
                # confidence: 1 = perfect match, 0 = no match
                distance = chunk.get("cosine_distance", 1.0)
                confidence = max(0.0, 1.0 - distance)

                ev = Evidence(
                    project_id=project_id,
                    section_version_id=section_version_id,
                    source_document_id=chunk.get("source_document_id"),
                    chunk_id=chunk.get("chunk_id"),
                    quote_text=chunk.get("content", "")[:500],
                    locator_json={"chunk_index": chunk.get("chunk_index")},
                    confidence=round(confidence, 4),
                )
                db.add(ev)
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
            }

        db.commit()

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "Persisted section %s version %d (run=%s, evidence=%d)",
            section_key,
            next_ver,
            run_id,
            len(evidence_chunks),
        )

        history = record_agent_call(
            agent="persist_result",
            action="persist_to_db",
            input_summary=(
                f"section={section_key}, run_id={run_id}, "
                f"draft_len={len(draft_markdown)}, evidence={len(evidence_chunks)}, "
                f"iteration={iteration}"
            ),
            output_summary=(
                f"section_version_id={section_version_id}, "
                f"version_number={next_ver}, persisted=True"
            ),
            duration_ms=duration_ms,
            success=True,
        )

        return {
            "section_version_id": section_version_id,
            "persisted": True,
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
