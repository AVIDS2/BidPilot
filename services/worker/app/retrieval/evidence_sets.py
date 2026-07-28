"""Durable, scope-checked evidence snapshots for drafting workflows.

Retrieval candidates are intentionally ephemeral. Before a model sees them we
capture a bounded ``EvidenceSet`` against the project, document version, chunk
and locator that were actually selected. Every later workflow stage reloads the
snapshot instead of trusting a mutable LangGraph state payload.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Bundle,
    EvidenceSet,
    EvidenceSetItem,
    ExecutionRun,
    KnowledgeChunk,
    RequirementItem,
    SourceDocument,
)
from contracts import CitationLocator, CitationValidationStatus, RetrievalCandidate


class EvidenceSetScopeError(ValueError):
    """Raised when an evidence set or run is not valid for the requested project."""


@dataclass(frozen=True)
class EvidenceSetItemSnapshot:
    id: str
    chunk_id: str
    source_document_id: str
    source_document_version: int
    source_document_checksum: str
    quote_text: str
    locator_json: dict
    retrieval_rank: int
    retrieval_score: float
    retrieval_methods: tuple[str, ...]
    selected_reason: str

    def as_state_chunk(self) -> dict:
        locator = dict(self.locator_json)
        chunk_index = locator.get("chunk_index")
        return {
            "evidence_set_item_id": self.id,
            "chunk_id": self.chunk_id,
            "source_document_id": self.source_document_id,
            "source_document_version": self.source_document_version,
            "content": self.quote_text,
            "retrieval_score": self.retrieval_score,
            "retrieval_methods": list(self.retrieval_methods),
            "locator_json": locator,
            "chunk_index": chunk_index if isinstance(chunk_index, int) else 0,
        }


@dataclass(frozen=True)
class EvidenceSetSnapshot:
    id: str
    status: str
    degraded_reasons: tuple[str, ...]
    rejected_reasons: tuple[str, ...]
    unmet_requirement_ids: tuple[str, ...]
    items: tuple[EvidenceSetItemSnapshot, ...]

    @property
    def evidence_chunks(self) -> list[dict]:
        return [item.as_state_chunk() for item in self.items]


@dataclass(frozen=True)
class _ValidatedCandidate:
    chunk: KnowledgeChunk
    document: SourceDocument
    locator: CitationLocator
    retrieval_rank: int
    retrieval_score: float
    retrieval_methods: tuple[str, ...]
    selected_reason: str


def _normalized(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).casefold().split())


def _dedupe_strings(values: Iterable[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        item = value.strip()
        if item and item not in result:
            result.append(item)
    return result


def _metadata_string(metadata: dict | None, key: str) -> str | None:
    if not isinstance(metadata, dict):
        return None
    value = metadata.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _metadata_int(metadata: dict | None, key: str) -> int | None:
    if not isinstance(metadata, dict):
        return None
    value = metadata.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _source_has_successor(db: Session, source_document_id: str) -> bool:
    return (
        db.scalar(
            select(SourceDocument.id)
            .where(SourceDocument.supersedes_document_id == source_document_id)
            .limit(1)
        )
        is not None
    )


def _load_chunk_scope(
    db: Session,
    chunk_id: str,
) -> tuple[KnowledgeChunk, SourceDocument, Bundle] | None:
    return db.execute(
        select(KnowledgeChunk, SourceDocument, Bundle)
        .join(SourceDocument, SourceDocument.id == KnowledgeChunk.source_document_id)
        .join(Bundle, Bundle.id == SourceDocument.bundle_id)
        .where(KnowledgeChunk.id == chunk_id)
    ).one_or_none()


def _validate_locator(
    *,
    locator: CitationLocator,
    chunk: KnowledgeChunk,
    document: SourceDocument,
) -> str | None:
    if locator.validation_status is CitationValidationStatus.INVALID:
        return locator.validation_reason or "invalid_citation_locator"
    if locator.source_document_id != document.id:
        return "locator_source_document_mismatch"
    if locator.chunk_index != chunk.chunk_index:
        return "locator_chunk_index_mismatch"
    if document.page_count is not None and locator.page is not None and locator.page > document.page_count:
        return "locator_page_out_of_range"
    if locator.text_anchor and _normalized(locator.text_anchor) not in _normalized(chunk.content):
        return "locator_text_anchor_not_found"

    metadata = chunk.metadata_json if isinstance(chunk.metadata_json, dict) else None
    metadata_source_id = _metadata_string(metadata, "source_document_id")
    if metadata_source_id is not None and metadata_source_id != document.id:
        return "metadata_source_document_mismatch"
    metadata_version = _metadata_int(metadata, "document_version")
    if metadata_version is not None and metadata_version != document.version_number:
        return "metadata_document_version_mismatch"
    metadata_checksum = _metadata_string(metadata, "document_checksum")
    if metadata_checksum is not None and metadata_checksum != document.checksum:
        return "metadata_document_checksum_mismatch"
    return None


def _validate_candidate(
    db: Session,
    *,
    project_id: str,
    candidate: RetrievalCandidate,
) -> tuple[_ValidatedCandidate | None, str | None]:
    record = _load_chunk_scope(db, candidate.chunk_id)
    if record is None:
        return None, "knowledge_chunk_not_found"
    chunk, document, bundle = record
    if (
        candidate.project_id != project_id
        or chunk.project_id != project_id
        or bundle.project_id != project_id
    ):
        return None, "cross_project_evidence"
    if candidate.source_document_id != document.id or chunk.source_document_id != document.id:
        return None, "candidate_source_document_mismatch"
    if _source_has_successor(db, document.id):
        return None, "source_document_superseded"
    locator_error = _validate_locator(locator=candidate.locator, chunk=chunk, document=document)
    if locator_error is not None:
        return None, locator_error

    methods = tuple(candidate.methods)
    selected_reason = (
        f"selected by {','.join(methods)}; rank={candidate.fused_rank}; "
        f"score={candidate.final_score:.6f}"
    )
    return (
        _ValidatedCandidate(
            chunk=chunk,
            document=document,
            locator=candidate.locator,
            retrieval_rank=candidate.fused_rank,
            retrieval_score=candidate.final_score,
            retrieval_methods=methods,
            selected_reason=selected_reason,
        ),
        None,
    )


def _relevant_requirement_ids(db: Session, project_id: str, section_key: str) -> list[str]:
    return list(
        db.scalars(
            select(RequirementItem.id).where(
                RequirementItem.project_id == project_id,
                RequirementItem.section_key.in_((section_key, "extracted")),
            )
        ).all()
    )


def _snapshot_from_set(
    db: Session,
    *,
    evidence_set: EvidenceSet,
    project_id: str,
) -> EvidenceSetSnapshot:
    if evidence_set.project_id != project_id:
        raise EvidenceSetScopeError("evidence_set_project_scope_invalid")

    accepted_items: list[EvidenceSetItemSnapshot] = []
    invalidated_reasons: list[str] = []
    rows = list(
        db.scalars(
            select(EvidenceSetItem)
            .where(EvidenceSetItem.evidence_set_id == evidence_set.id)
            .order_by(EvidenceSetItem.retrieval_rank.asc(), EvidenceSetItem.id.asc())
        ).all()
    )
    for item in rows:
        record = _load_chunk_scope(db, item.chunk_id)
        if record is None:
            invalidated_reasons.append("knowledge_chunk_not_found")
            continue
        chunk, document, bundle = record
        if (
            chunk.project_id != project_id
            or bundle.project_id != project_id
            or chunk.source_document_id != item.source_document_id
            or document.id != item.source_document_id
        ):
            invalidated_reasons.append("cross_project_evidence")
            continue
        if _source_has_successor(db, document.id):
            invalidated_reasons.append("source_document_superseded")
            continue
        if (
            document.version_number != item.source_document_version
            or document.checksum != item.source_document_checksum
        ):
            invalidated_reasons.append("source_document_version_changed")
            continue
        try:
            locator = CitationLocator.model_validate(item.locator_json)
        except (TypeError, ValueError):
            invalidated_reasons.append("stored_locator_invalid")
            continue
        locator_error = _validate_locator(locator=locator, chunk=chunk, document=document)
        if locator_error is not None:
            invalidated_reasons.append(locator_error)
            continue
        if _normalized(item.quote_text) not in _normalized(chunk.content):
            invalidated_reasons.append("evidence_quote_no_longer_matches_chunk")
            continue
        accepted_items.append(
            EvidenceSetItemSnapshot(
                id=item.id,
                chunk_id=item.chunk_id,
                source_document_id=item.source_document_id,
                source_document_version=item.source_document_version,
                source_document_checksum=item.source_document_checksum,
                quote_text=item.quote_text,
                locator_json=dict(item.locator_json),
                retrieval_rank=item.retrieval_rank,
                retrieval_score=item.retrieval_score,
                retrieval_methods=tuple(_dedupe_strings(item.retrieval_methods_json or [])),
                selected_reason=item.selected_reason,
            )
        )

    rejected_reasons = _dedupe_strings(
        [*(evidence_set.rejected_reasons_json or []), *invalidated_reasons]
    )
    if invalidated_reasons:
        evidence_set.rejected_reasons_json = rejected_reasons
        evidence_set.status = "invalidated" if not accepted_items else "degraded"
    elif not accepted_items and evidence_set.status == "ready":
        evidence_set.status = "missing_evidence"

    return EvidenceSetSnapshot(
        id=evidence_set.id,
        status=evidence_set.status,
        degraded_reasons=tuple(_dedupe_strings(evidence_set.degraded_reasons_json or [])),
        rejected_reasons=tuple(rejected_reasons),
        unmet_requirement_ids=tuple(_dedupe_strings(evidence_set.unmet_requirement_ids_json or [])),
        items=tuple(accepted_items),
    )


def capture_evidence_set(
    db: Session,
    *,
    project_id: str,
    execution_run_id: str,
    section_key: str,
    query_text: str,
    retrieval_profile_id: str | None,
    degraded_reasons: Iterable[str],
    candidates: Iterable[RetrievalCandidate],
) -> EvidenceSetSnapshot:
    """Persist a bounded, validated evidence snapshot before model drafting.

    Replays for the same execution run reuse the first successful snapshot.
    This makes a retry deterministic instead of silently retrieving a new set
    of sources between provider attempts.
    """
    run = db.get(ExecutionRun, execution_run_id)
    if run is None or run.project_id != project_id:
        raise EvidenceSetScopeError("execution_run_project_scope_invalid")

    existing = db.scalar(
        select(EvidenceSet).where(
            EvidenceSet.execution_run_id == execution_run_id,
            EvidenceSet.section_key == section_key,
        )
    )
    if existing is not None:
        return _snapshot_from_set(db, evidence_set=existing, project_id=project_id)

    evidence_set = EvidenceSet(
        project_id=project_id,
        execution_run_id=execution_run_id,
        section_key=section_key,
        query_text=query_text,
        retrieval_profile_id=retrieval_profile_id,
        status="ready",
        degraded_reasons_json=_dedupe_strings(degraded_reasons),
        rejected_reasons_json=[],
        unmet_requirement_ids_json=[],
    )
    rejected_reasons: list[str] = []
    accepted_count = 0
    try:
        with db.begin_nested():
            db.add(evidence_set)
            db.flush()
            for candidate in candidates:
                validated, rejection_reason = _validate_candidate(
                    db,
                    project_id=project_id,
                    candidate=candidate,
                )
                if validated is None:
                    if rejection_reason is not None:
                        rejected_reasons.append(rejection_reason)
                    continue
                db.add(
                    EvidenceSetItem(
                        evidence_set_id=evidence_set.id,
                        source_document_id=validated.document.id,
                        chunk_id=validated.chunk.id,
                        source_document_version=validated.document.version_number,
                        source_document_checksum=validated.document.checksum,
                        locator_json=validated.locator.model_dump(exclude_none=True),
                        quote_text=validated.chunk.content[:1000],
                        retrieval_rank=validated.retrieval_rank,
                        retrieval_score=validated.retrieval_score,
                        retrieval_methods_json=list(validated.retrieval_methods),
                        selected_reason=validated.selected_reason,
                    )
                )
                accepted_count += 1
            evidence_set.rejected_reasons_json = _dedupe_strings(rejected_reasons)
            if not accepted_count:
                evidence_set.status = "missing_evidence"
                evidence_set.unmet_requirement_ids_json = _relevant_requirement_ids(
                    db,
                    project_id,
                    section_key,
                )
            elif rejected_reasons:
                evidence_set.status = "degraded"
            db.flush()
    except IntegrityError:
        # A duplicate delivery may race between two workers. The unique run /
        # section key decides the canonical snapshot; retries must reuse it.
        existing = db.scalar(
            select(EvidenceSet).where(
                EvidenceSet.execution_run_id == execution_run_id,
                EvidenceSet.section_key == section_key,
            )
        )
        if existing is None:
            raise
        return _snapshot_from_set(db, evidence_set=existing, project_id=project_id)

    return _snapshot_from_set(db, evidence_set=evidence_set, project_id=project_id)


def load_authorized_evidence_set(
    db: Session,
    *,
    evidence_set_id: str,
    project_id: str,
    execution_run_id: str | None = None,
) -> EvidenceSetSnapshot:
    """Reload and revalidate an evidence snapshot before each sensitive use."""
    evidence_set = db.get(EvidenceSet, evidence_set_id)
    if evidence_set is None:
        raise EvidenceSetScopeError("evidence_set_not_found")
    if execution_run_id is not None and evidence_set.execution_run_id != execution_run_id:
        raise EvidenceSetScopeError("evidence_set_execution_run_scope_invalid")
    return _snapshot_from_set(db, evidence_set=evidence_set, project_id=project_id)


__all__ = [
    "EvidenceSetItemSnapshot",
    "EvidenceSetScopeError",
    "EvidenceSetSnapshot",
    "capture_evidence_set",
    "load_authorized_evidence_set",
]
