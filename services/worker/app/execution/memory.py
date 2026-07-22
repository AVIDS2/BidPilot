"""Bounded, evidence-first Bid Wiki compilation and memory vector indexing."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy import or_, select

from app.adapters.embedding import generate_embeddings_batch, get_embedding_profile
from app.db import SessionLocal
from app.execution.embedding_capacity import (
    EmbeddingCapacityUnavailable,
    begin_official_embedding_call,
    finalize_official_embedding_call,
)
from app.models import (
    Bundle,
    KnowledgeChunk,
    MemoryCompilationRun,
    MemoryEvent,
    MemoryEvidenceLink,
    MemoryRecord,
    SourceDocument,
)
from app.retrieval.normalization import normalize_retrieval_text
from contracts import EmbeddingOutcomeStatus, MemoryKind, MemoryProposal, MemoryProposalOrigin, MemoryScope


logger = logging.getLogger(__name__)

_COMPILER_POLICY_VERSION = "memory-compiler-v1"
_MAX_SOURCE_CHUNKS = 3
_MAX_EXCERPT_CHARACTERS = 540


def _utc_naive_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _fingerprint(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _excerpt(value: str, *, limit: int = _MAX_EXCERPT_CHARACTERS) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def _locator(chunk: KnowledgeChunk) -> dict[str, object]:
    metadata = chunk.metadata_json if isinstance(chunk.metadata_json, dict) else {}
    locator: dict[str, object] = {
        "source_document_id": chunk.source_document_id,
        "chunk_index": chunk.chunk_index,
        "text_anchor": chunk.content[:240].strip(),
    }
    for key in ("page", "heading_path", "table_headers"):
        if key in metadata:
            locator[key] = metadata[key]
    return locator


def _mark_compilation_failed(compilation_run_id: str, error_code: str) -> dict[str, str]:
    db = SessionLocal()
    try:
        run = db.get(MemoryCompilationRun, compilation_run_id)
        if run is not None:
            run.status = "failed"
            run.error_code = error_code
            run.finished_at = _utc_naive_now()
            db.commit()
    finally:
        db.close()
    return {"compilation_run_id": compilation_run_id, "status": "failed", "error_code": error_code}


def run_compile_bid_wiki(compilation_run_id: str) -> dict[str, str]:
    """Create source-backed *proposals* from already parsed project material.

    This deliberately does not parse files, call an LLM, or activate memory.
    It creates one bounded summary proposal per source snapshot so reviewers can
    decide what belongs in the shared Bid Wiki.
    """
    db = SessionLocal()
    try:
        run = db.get(MemoryCompilationRun, compilation_run_id)
        if run is None:
            return {"compilation_run_id": compilation_run_id, "status": "not_found"}
        if run.status not in {"queued", "retryable"}:
            return {"compilation_run_id": compilation_run_id, "status": run.status}
        if run.policy_version != _COMPILER_POLICY_VERSION:
            return _mark_compilation_failed(compilation_run_id, "unsupported_policy_version")

        bundle = db.get(Bundle, run.bundle_id) if run.bundle_id else None
        if bundle is not None and bundle.project_id != run.project_id:
            return _mark_compilation_failed(compilation_run_id, "invalid_bundle_scope")

        source_ids = tuple(
            sorted({source_id for source_id in run.input_source_ids_json if isinstance(source_id, str) and source_id})
        )
        if not source_ids:
            return _mark_compilation_failed(compilation_run_id, "missing_source_input")

        run.status = "running"
        run.started_at = _utc_naive_now()
        db.commit()

        sources_stmt = (
            select(SourceDocument)
            .join(Bundle, Bundle.id == SourceDocument.bundle_id)
            .where(
                Bundle.project_id == run.project_id,
                SourceDocument.id.in_(source_ids),
                SourceDocument.parse_status == "parsed",
            )
            .order_by(SourceDocument.id.asc())
        )
        if bundle is not None:
            sources_stmt = sources_stmt.where(Bundle.id == bundle.id)
        sources = list(db.scalars(sources_stmt).all())
        known_fingerprints = set(
            db.scalars(
                select(MemoryRecord.content_fingerprint).where(
                    MemoryRecord.project_id == run.project_id,
                    MemoryRecord.content_fingerprint.isnot(None),
                )
            ).all()
        )

        created_count = 0
        skipped_count = 0
        for source in sources:
            chunks = list(
                db.scalars(
                    select(KnowledgeChunk)
                    .where(
                        KnowledgeChunk.project_id == run.project_id,
                        KnowledgeChunk.source_document_id == source.id,
                    )
                    .order_by(KnowledgeChunk.chunk_index.asc(), KnowledgeChunk.id.asc())
                    .limit(_MAX_SOURCE_CHUNKS)
                ).all()
            )
            if not chunks:
                skipped_count += 1
                continue

            fingerprint = _fingerprint(
                _COMPILER_POLICY_VERSION,
                run.project_id,
                source.id,
                *(chunk.id for chunk in chunks),
            )
            if fingerprint in known_fingerprints:
                skipped_count += 1
                continue

            body = "\n\n".join(f"- {_excerpt(chunk.content)}" for chunk in chunks)
            evidence_ids = tuple(chunk.id for chunk in chunks)
            proposal = MemoryProposal(
                org_id=run.org_id,
                project_id=run.project_id,
                owner_user_id=None,
                scope=MemoryScope.PROJECT_SHARED,
                kind=MemoryKind.SUMMARY,
                title=f"{source.original_filename[:180]} · 资料摘要",
                body_markdown=body,
                structured_data_json={
                    "source_document_id": source.id,
                    "source_chunk_ids": list(evidence_ids),
                    "compiler_policy_version": _COMPILER_POLICY_VERSION,
                },
                origin=MemoryProposalOrigin.SYSTEM,
                evidence_ids=evidence_ids,
            )
            record = MemoryRecord(
                org_id=proposal.org_id,
                project_id=proposal.project_id,
                owner_user_id=None,
                scope=proposal.scope.value,
                kind=proposal.kind.value,
                status="proposed",
                title=proposal.title,
                body_markdown=proposal.body_markdown,
                structured_data_json=proposal.structured_data_json,
                content_fingerprint=fingerprint,
                retrieval_text=normalize_retrieval_text(f"{proposal.title}\n{proposal.body_markdown}"),
                embedding_status="pending",
                origin=proposal.origin.value,
                created_by_actor_type="system",
                created_by_actor_id="memory-compiler",
            )
            db.add(record)
            db.flush()
            for chunk in chunks:
                db.add(
                    MemoryEvidenceLink(
                        memory_record_id=record.id,
                        source_type="knowledge_chunk",
                        source_id=chunk.id,
                        label=f"{source.original_filename} · 片段 {chunk.chunk_index + 1}",
                        locator_json=_locator(chunk),
                    )
                )
            db.add(
                MemoryEvent(
                    memory_record_id=record.id,
                    org_id=record.org_id,
                    project_id=record.project_id,
                    actor_type="system",
                    actor_id="memory-compiler",
                    event_type="memory.proposed_by_compiler",
                    payload_json={"compilation_run_id": run.id, "source_document_id": source.id},
                )
            )
            known_fingerprints.add(fingerprint)
            created_count += 1

        run.status = "succeeded"
        run.finished_at = _utc_naive_now()
        run.result_json = {
            "proposals_created": created_count,
            "proposals_skipped": skipped_count,
            "source_documents_seen": len(sources),
        }
        db.commit()
        return {
            "compilation_run_id": run.id,
            "status": "succeeded",
            "proposals_created": str(created_count),
            "proposals_skipped": str(skipped_count),
        }
    except Exception:
        db.rollback()
        logger.exception("Bid Wiki compilation failed for run %s", compilation_run_id)
        return _mark_compilation_failed(compilation_run_id, "compilation_failed")
    finally:
        db.close()


def index_memory_records(memory_record_ids: list[str]) -> dict[str, str]:
    """Index active memory without mixing tenant content in provider batches.

    Every provider request is scoped to one organization, project, and private
    owner boundary. A failed or budget-limited refresh only changes the
    retrieval state; it never clears an already valid vector.
    """
    profile = get_embedding_profile()
    if profile is None:
        return {"status": "not_configured", "indexed": "0", "failed": "0"}
    record_ids = tuple(sorted({record_id for record_id in memory_record_ids if record_id}))
    if not record_ids:
        return {"status": "completed", "indexed": "0", "failed": "0"}

    db = SessionLocal()
    try:
        records = list(
            db.scalars(
                select(MemoryRecord)
                .where(
                    MemoryRecord.id.in_(record_ids),
                    MemoryRecord.status == "active",
                    MemoryRecord.deleted_at.is_(None),
                    or_(
                        MemoryRecord.embedding.is_(None),
                        MemoryRecord.embedding_status != "success",
                        MemoryRecord.embedding_profile.is_distinct_from(profile.identifier),
                    ),
                )
                .order_by(MemoryRecord.id.asc())
            ).all()
        )
        if not records:
            return {"status": "completed", "indexed": "0", "failed": "0"}

        indexed_count = 0
        failed_count = 0
        groups: dict[tuple[str, str, str | None], list[MemoryRecord]] = {}
        for record in records:
            groups.setdefault((record.org_id, record.project_id, record.owner_user_id), []).append(record)

        def reload_group(record_group: list[MemoryRecord]) -> list[MemoryRecord]:
            record_ids_for_group = [record.id for record in record_group]
            by_id = {
                record.id: record
                for record in db.scalars(
                    select(MemoryRecord).where(MemoryRecord.id.in_(record_ids_for_group))
                ).all()
            }
            return [by_id[record_id] for record_id in record_ids_for_group if record_id in by_id]

        def mark_group_failure(
            record_group: list[MemoryRecord],
            *,
            status: EmbeddingOutcomeStatus,
            error_code: str,
        ) -> int:
            indexed_at = _utc_naive_now()
            for record in record_group:
                record.retrieval_text = normalize_retrieval_text(f"{record.title}\n{record.body_markdown}")
                record.embedding_status = status.value
                record.embedding_updated_at = indexed_at
                record.embedding_error_code = error_code
            return len(record_group)

        for (org_id, project_id, owner_user_id), record_group in groups.items():
            texts = [f"{record.title}\n{record.body_markdown}" for record in record_group]
            try:
                metering_context = begin_official_embedding_call(
                    db,
                    org_id=org_id,
                    user_id=owner_user_id,
                    project_id=project_id,
                    workload="embedding_memory_index",
                    texts=texts,
                    provider_type=profile.provider,
                    model_name=profile.model,
                )
                # Never release private source text until the shared capacity hold is durable.
                db.commit()
            except EmbeddingCapacityUnavailable as exc:
                db.rollback()
                failed_count += mark_group_failure(
                    reload_group(record_group),
                    status=EmbeddingOutcomeStatus.BUDGET_EXHAUSTED,
                    error_code=exc.error_code,
                )
                db.commit()
                continue
            except Exception:
                db.rollback()
                logger.exception("Memory embedding capacity preflight failed for org %s", org_id)
                failed_count += mark_group_failure(
                    reload_group(record_group),
                    status=EmbeddingOutcomeStatus.TRANSIENT_FAILURE,
                    error_code="embedding_metering_unavailable",
                )
                db.commit()
                continue

            outcomes = generate_embeddings_batch(texts)
            if len(outcomes) != len(record_group):
                logger.warning("Memory embedding provider returned an incomplete batch for org %s", org_id)
                failed_count += mark_group_failure(
                    record_group,
                    status=EmbeddingOutcomeStatus.TRANSIENT_FAILURE,
                    error_code="embedding_incomplete_response",
                )
                finalize_official_embedding_call(db, context=metering_context, outcomes=[])
                db.commit()
                continue

            indexed_at = _utc_naive_now()
            for record, outcome in zip(record_group, outcomes):
                record.retrieval_text = normalize_retrieval_text(f"{record.title}\n{record.body_markdown}")
                record.embedding_status = outcome.status.value
                record.embedding_updated_at = indexed_at
                record.embedding_error_code = outcome.error_code
                if outcome.is_success and outcome.embedding is not None:
                    record.embedding = outcome.embedding
                    record.embedding_profile = outcome.profile_id
                    indexed_count += 1
                else:
                    failed_count += 1
            finalize_official_embedding_call(db, context=metering_context, outcomes=outcomes)
            db.commit()
        return {"status": "completed", "indexed": str(indexed_count), "failed": str(failed_count)}
    except Exception:
        db.rollback()
        logger.exception("Memory indexing failed")
        return {"status": "failed", "indexed": "0", "failed": str(len(record_ids))}
    finally:
        db.close()
