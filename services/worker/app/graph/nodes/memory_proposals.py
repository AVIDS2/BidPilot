"""Create reviewable memory proposals from successful, evidence-backed workflows."""

from __future__ import annotations

import hashlib
import logging
import time

from sqlalchemy import select

from app.db import SessionLocal
from app.models import MemoryEvent, MemoryEvidenceLink, MemoryRecord, Project
from app.retrieval.normalization import normalize_retrieval_text

from ..state import BidPilotState
from ._history import record_agent_call


logger = logging.getLogger(__name__)
_POLICY_VERSION = "workflow-memory-proposal-v1"
_MAX_DRAFT_CHARACTERS = 1_600
_MAX_EVIDENCE_LINKS = 5


def _fingerprint(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _proposal_is_eligible(state: BidPilotState) -> bool:
    return bool(
        state.get("persisted")
        and state.get("review_passed")
        and state.get("human_decision") == "approved"
        and state.get("section_version_id")
        and state.get("draft_markdown")
        and state.get("evidence_chunks")
    )


def propose_memory_updates_node(state: BidPilotState) -> dict:
    """Propose, never activate, a workflow-derived project summary.

    The output can help reviewers maintain the Bid Wiki, but it is not treated
    as a source of truth until a project approver accepts it through the ledger.
    """
    started = time.monotonic()
    if not _proposal_is_eligible(state):
        history = record_agent_call(
            agent="memory_proposals",
            action="propose_workflow_memory",
            input_summary="workflow output is not eligible for automatic proposal",
            output_summary="proposal_skipped=not_approved_or_missing_evidence",
            duration_ms=int((time.monotonic() - started) * 1000),
            success=True,
        )
        return {"memory_proposal_ids": [], "agent_history": history}

    project_id = state["project_id"]
    section_key = state["section_key"]
    section_version_id = str(state["section_version_id"])
    evidence_chunks = state.get("evidence_chunks", [])[:_MAX_EVIDENCE_LINKS]
    evidence_ids = [
        str(chunk.get("chunk_id"))
        for chunk in evidence_chunks
        if isinstance(chunk, dict) and chunk.get("chunk_id")
    ]
    if not evidence_ids:
        return {"memory_proposal_ids": [], "agent_history": []}

    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project is None:
            raise ValueError("project_not_found")
        fingerprint = _fingerprint(
            _POLICY_VERSION,
            project.id,
            section_version_id,
            *sorted(evidence_ids),
        )
        existing = db.scalar(
            select(MemoryRecord.id).where(MemoryRecord.content_fingerprint == fingerprint).limit(1)
        )
        if existing is not None:
            history = record_agent_call(
                agent="memory_proposals",
                action="propose_workflow_memory",
                input_summary=f"section_version={section_version_id}",
                output_summary="proposal_skipped=duplicate_snapshot",
                duration_ms=int((time.monotonic() - started) * 1000),
                success=True,
            )
            return {"memory_proposal_ids": [], "agent_history": history}

        draft_excerpt = str(state.get("draft_markdown") or "").strip()[:_MAX_DRAFT_CHARACTERS]
        title = f"章节提要 · {section_key.replace('-', ' ')}"
        record = MemoryRecord(
            org_id=project.org_id,
            project_id=project.id,
            scope="project_shared",
            kind="summary",
            status="proposed",
            title=title,
            body_markdown=draft_excerpt,
            structured_data_json={
                "section_key": section_key,
                "section_version_id": section_version_id,
                "workflow_memory_policy_version": _POLICY_VERSION,
            },
            content_fingerprint=fingerprint,
            retrieval_text=normalize_retrieval_text(f"{title}\n{draft_excerpt}"),
            embedding_status="pending",
            origin="system",
            created_by_actor_type="system",
            created_by_actor_id="workflow-memory",
        )
        db.add(record)
        db.flush()
        for chunk in evidence_chunks:
            if not isinstance(chunk, dict) or not chunk.get("chunk_id"):
                continue
            source_document_id = chunk.get("source_document_id")
            locator = chunk.get("locator_json")
            db.add(
                MemoryEvidenceLink(
                    memory_record_id=record.id,
                    source_type="knowledge_chunk",
                    source_id=str(chunk["chunk_id"]),
                    label=(
                        f"工作流章节 {section_key} · "
                        f"资料片段 {chunk.get('chunk_index', '?')}"
                    ),
                    locator_json={
                        "source_document_id": source_document_id,
                        **(locator if isinstance(locator, dict) else {}),
                    },
                )
            )
        db.add(
            MemoryEvent(
                memory_record_id=record.id,
                org_id=project.org_id,
                project_id=project.id,
                actor_type="system",
                actor_id="workflow-memory",
                event_type="memory.proposed_by_workflow",
                payload_json={"section_version_id": section_version_id, "section_key": section_key},
            )
        )
        db.commit()
        history = record_agent_call(
            agent="memory_proposals",
            action="propose_workflow_memory",
            input_summary=f"section_version={section_version_id}, evidence={len(evidence_ids)}",
            output_summary=f"proposal_id={record.id}, status=proposed",
            duration_ms=int((time.monotonic() - started) * 1000),
            success=True,
        )
        return {"memory_proposal_ids": [record.id], "agent_history": history}
    except Exception:
        db.rollback()
        logger.exception("Workflow memory proposal failed")
        history = record_agent_call(
            agent="memory_proposals",
            action="propose_workflow_memory",
            input_summary=f"section={section_key}",
            output_summary="proposal_skipped=unavailable",
            duration_ms=int((time.monotonic() - started) * 1000),
            success=False,
            error="memory_proposal_unavailable",
        )
        # A proposal failure must not invalidate an already persisted deliverable.
        return {"memory_proposal_ids": [], "agent_history": history}
    finally:
        db.close()
