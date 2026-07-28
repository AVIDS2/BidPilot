"""Durable source-document ingestion: parse, persist, index, and classify state."""

import hashlib
import logging
from datetime import UTC, datetime

from app.adapters.embedding import generate_embeddings_batch, get_embedding_profile
from app.adapters.parser import parse_bundle_documents, store_chunks
from app.adapters.requirements import RequirementSource, extract_requirements
from app.db import SessionLocal
from app.execution.embedding_capacity import (
    EmbeddingCapacityUnavailable,
    begin_official_embedding_call,
    finalize_official_embedding_call,
)
from app.models import (
    BidRequirementProfile,
    Bundle,
    KnowledgeChunk,
    Project,
    RequirementItem,
    SourceDocument,
)
from app.retrieval.normalization import normalize_retrieval_text
from contracts import EmbeddingOutcomeStatus
from contracts.document_ingestion import (
    BundleIngestStatus,
    DocumentIndexStatus,
    DocumentParseStatus,
    MAX_DOCUMENT_PARSE_ATTEMPTS,
)
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


def _embed_and_update_chunks(bundle_id: str) -> int:
    """Index only pending, failed, or profile-stale chunks without losing a good vector."""
    db = SessionLocal()
    try:
        profile = get_embedding_profile()
        stale_chunk_predicate = or_(
            KnowledgeChunk.embedding.is_(None),
            KnowledgeChunk.embedding_status != EmbeddingOutcomeStatus.SUCCESS.value,
        )
        if profile is not None:
            stale_chunk_predicate = or_(
                stale_chunk_predicate,
                KnowledgeChunk.embedding_profile.is_distinct_from(profile.identifier),
            )
        stmt = (
            select(KnowledgeChunk)
            .join(SourceDocument, SourceDocument.id == KnowledgeChunk.source_document_id)
            .where(SourceDocument.bundle_id == bundle_id)
            .where(stale_chunk_predicate)
        )
        chunks = list(db.scalars(stmt).all())
        if not chunks:
            return 0
        if profile is None:
            # Preserve a usable vector that was already successfully indexed,
            # but make each pending/retryable chunk visibly actionable.
            indexed_at = datetime.now(UTC).replace(tzinfo=None)
            for chunk in chunks:
                chunk.retrieval_text = normalize_retrieval_text(chunk.content)
                chunk.embedding_status = EmbeddingOutcomeStatus.NOT_CONFIGURED.value
                chunk.embedding_updated_at = indexed_at
                chunk.embedding_error_code = "embedding_provider_unconfigured"
            db.commit()
            return 0
        chunk_ids = [chunk.id for chunk in chunks]
        project_id = chunks[0].project_id
        project = db.get(Project, project_id)
        if project is None:
            logger.warning("Cannot meter embeddings without project context for bundle %s", bundle_id)
            return 0

        texts = [c.content for c in chunks]
        try:
            metering_context = begin_official_embedding_call(
                db,
                org_id=project.org_id,
                user_id=None,
                project_id=project_id,
                workload="embedding_bundle_index",
                texts=texts,
                provider_type=profile.provider,
                model_name=profile.model,
            )
            # The reservation must be visible before the provider receives text.
            db.commit()
        except EmbeddingCapacityUnavailable as exc:
            db.rollback()
            chunks = list(
                db.scalars(
                    select(KnowledgeChunk)
                    .where(KnowledgeChunk.id.in_(chunk_ids))
                    .order_by(KnowledgeChunk.id.asc())
                ).all()
            )
            indexed_at = datetime.now(UTC).replace(tzinfo=None)
            for chunk in chunks:
                chunk.retrieval_text = normalize_retrieval_text(chunk.content)
                chunk.embedding_status = EmbeddingOutcomeStatus.BUDGET_EXHAUSTED.value
                chunk.embedding_updated_at = indexed_at
                chunk.embedding_error_code = exc.error_code
            db.commit()
            return 0
        except Exception:
            db.rollback()
            logger.exception("Embedding capacity preflight failed for bundle %s", bundle_id)
            chunks = list(
                db.scalars(
                    select(KnowledgeChunk)
                    .where(KnowledgeChunk.id.in_(chunk_ids))
                    .order_by(KnowledgeChunk.id.asc())
                ).all()
            )
            indexed_at = datetime.now(UTC).replace(tzinfo=None)
            for chunk in chunks:
                chunk.retrieval_text = normalize_retrieval_text(chunk.content)
                chunk.embedding_status = EmbeddingOutcomeStatus.TRANSIENT_FAILURE.value
                chunk.embedding_updated_at = indexed_at
                chunk.embedding_error_code = "embedding_metering_unavailable"
            db.commit()
            return 0

        results = generate_embeddings_batch(texts)
        if len(results) != len(chunks):
            logger.warning("Embedding provider returned an incomplete result batch for bundle %s", bundle_id)
            indexed_at = datetime.now(UTC).replace(tzinfo=None)
            for chunk in chunks:
                chunk.retrieval_text = normalize_retrieval_text(chunk.content)
                chunk.embedding_status = EmbeddingOutcomeStatus.TRANSIENT_FAILURE.value
                chunk.embedding_updated_at = indexed_at
                chunk.embedding_error_code = "embedding_incomplete_response"
            finalize_official_embedding_call(
                db,
                context=metering_context,
                outcomes=[],
            )
            db.commit()
            return 0

        indexed_count = 0
        indexed_at = datetime.now(UTC).replace(tzinfo=None)
        for chunk, emb_result in zip(chunks, results):
            chunk.retrieval_text = normalize_retrieval_text(chunk.content)
            chunk.embedding_status = emb_result.status.value
            chunk.embedding_updated_at = indexed_at
            chunk.embedding_error_code = emb_result.error_code
            if emb_result.is_success and emb_result.embedding is not None:
                chunk.embedding = emb_result.embedding
                chunk.embedding_profile = emb_result.profile_id
                indexed_count += 1
        finalize_official_embedding_call(
            db,
            context=metering_context,
            outcomes=results,
        )
        db.commit()
        return indexed_count
    except Exception:
        logger.exception("Embedding step failed for bundle %s", bundle_id)
        _mark_embedding_failure(bundle_id, "embedding_step_failed")
        return 0
    finally:
        db.close()


def run_ingest(bundle_id: str) -> dict[str, str]:
    """Execute the full ingest pipeline for a bundle."""
    if not _begin_ingest(bundle_id):
        return {"bundle_id": bundle_id, "status": "not_found"}
    try:
        parsed = parse_bundle_documents(bundle_id)
        stored = store_chunks(bundle_id, parsed)
        embedded_count = _embed_and_update_chunks(bundle_id)
        req_count = _extract_and_store_requirements(
            bundle_id,
            source_document_ids=set(stored.parsed_document_ids),
        )
        bundle_status = _synchronize_document_index_state(bundle_id)
    except Exception:
        logger.exception("Bundle ingest failed for %s", bundle_id)
        _mark_ingest_failed(bundle_id, "ingest_worker_failed")
        return {"bundle_id": bundle_id, "status": BundleIngestStatus.FAILED.value}

    return {
        "bundle_id": bundle_id,
        "status": bundle_status,
        "chunks_created": str(stored.chunks_created),
        "chunks_embedded": str(embedded_count),
        "parsed_assets_created": str(stored.parsed_assets_created),
        "requirements_extracted": str(req_count),
    }


def run_reindex(bundle_id: str) -> dict[str, str]:
    """Refresh stale embeddings without parsing files or recreating requirements."""
    if not _begin_reindex(bundle_id):
        return {"bundle_id": bundle_id, "status": "not_found"}
    try:
        embedded_count = _embed_and_update_chunks(bundle_id)
        _synchronize_document_index_state(bundle_id)
    except Exception:
        logger.exception("Bundle reindex failed for %s", bundle_id)
        _mark_ingest_failed(bundle_id, "reindex_worker_failed")
        return {"bundle_id": bundle_id, "status": BundleIngestStatus.FAILED.value}

    return {
        "bundle_id": bundle_id,
        "status": "reindexed",
        "chunks_embedded": str(embedded_count),
    }


def _begin_ingest(bundle_id: str) -> bool:
    """Mark retryable documents as parsing before the pure parser runs."""
    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        if bundle is None:
            return False
        bundle.ingest_status = BundleIngestStatus.RUNNING.value
        for document in bundle.source_documents:
            if document.parse_status == DocumentParseStatus.PARSED.value:
                continue
            if document.parse_attempt_count >= MAX_DOCUMENT_PARSE_ATTEMPTS:
                # Preserve the parser's final classified cause when available;
                # a crash after reserving the last attempt gets a stable code.
                document.parse_status = DocumentParseStatus.FAILED.value
                document.parse_error_code = document.parse_error_code or "parse_retry_exhausted"
                continue
            document.parse_status = DocumentParseStatus.PARSING.value
            document.parse_error_code = None
            document.parse_attempt_count += 1
        db.commit()
        return True
    finally:
        db.close()


def _begin_reindex(bundle_id: str) -> bool:
    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        if bundle is None:
            return False
        bundle.ingest_status = BundleIngestStatus.INDEXING.value
        for document in bundle.source_documents:
            if document.parse_status == DocumentParseStatus.PARSED.value:
                document.index_status = DocumentIndexStatus.INDEXING.value
                document.index_error_code = None
        db.commit()
        return True
    finally:
        db.close()


def _mark_embedding_failure(bundle_id: str, error_code: str) -> None:
    """Expose an unexpected index failure without overwriting a good vector."""
    db = SessionLocal()
    try:
        chunks = list(
            db.scalars(
                select(KnowledgeChunk)
                .join(SourceDocument, SourceDocument.id == KnowledgeChunk.source_document_id)
                .where(SourceDocument.bundle_id == bundle_id)
                .where(
                    or_(
                        KnowledgeChunk.embedding.is_(None),
                        KnowledgeChunk.embedding_status != EmbeddingOutcomeStatus.SUCCESS.value,
                    )
                )
            ).all()
        )
        indexed_at = datetime.now(UTC).replace(tzinfo=None)
        for chunk in chunks:
            chunk.retrieval_text = normalize_retrieval_text(chunk.content)
            chunk.embedding_status = EmbeddingOutcomeStatus.TRANSIENT_FAILURE.value
            chunk.embedding_updated_at = indexed_at
            chunk.embedding_error_code = error_code
        db.commit()
    finally:
        db.close()


def _synchronize_document_index_state(bundle_id: str) -> str:
    """Derive document/bundle state from durable parse and chunk outcomes."""
    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        if bundle is None:
            return BundleIngestStatus.FAILED.value
        documents = list(bundle.source_documents)
        now = datetime.now(UTC).replace(tzinfo=None)
        has_problem = False

        for document in documents:
            if document.parse_status != DocumentParseStatus.PARSED.value:
                has_problem = True
                continue
            chunks = list(
                db.scalars(
                    select(KnowledgeChunk)
                    .where(KnowledgeChunk.source_document_id == document.id)
                    .order_by(KnowledgeChunk.chunk_index.asc())
                ).all()
            )
            if not chunks:
                document.index_status = DocumentIndexStatus.FAILED.value
                document.index_error_code = "no_persisted_chunks"
                document.indexed_at = now
                has_problem = True
                continue
            statuses = {chunk.embedding_status for chunk in chunks}
            error_code = next((chunk.embedding_error_code for chunk in chunks if chunk.embedding_error_code), None)
            if statuses == {EmbeddingOutcomeStatus.SUCCESS.value}:
                document.index_status = DocumentIndexStatus.INDEXED.value
                document.index_error_code = None
            elif EmbeddingOutcomeStatus.SUCCESS.value in statuses:
                document.index_status = DocumentIndexStatus.DEGRADED.value
                document.index_error_code = error_code or "partial_embedding_failure"
                has_problem = True
            else:
                document.index_status = DocumentIndexStatus.FAILED.value
                document.index_error_code = error_code or "embedding_not_available"
                has_problem = True
            document.indexed_at = now

        bundle.ingest_status = (
            BundleIngestStatus.PARTIAL_FAILURE.value
            if has_problem
            else BundleIngestStatus.INGESTED.value
        )
        db.commit()
        return bundle.ingest_status
    finally:
        db.close()


def _mark_ingest_failed(bundle_id: str, error_code: str) -> None:
    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        if bundle is None:
            return
        bundle.ingest_status = BundleIngestStatus.FAILED.value
        for document in bundle.source_documents:
            if document.parse_status == DocumentParseStatus.PARSING.value:
                document.parse_status = DocumentParseStatus.FAILED.value
                document.parse_error_code = error_code
        db.commit()
    finally:
        db.close()


def _extract_and_store_requirements(
    bundle_id: str,
    *,
    source_document_ids: set[str] | None = None,
) -> int:
    """Materialize source-backed requirement facts for newly parsed documents.

    This ingestion path is intentionally deterministic. Model-assisted analysis
    belongs to the governed workflow and may enrich planning, but it must not
    create a second, source-less requirement ledger.
    """
    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        if bundle is None:
            return 0
        project_id = bundle.project_id

        stmt = (
            select(KnowledgeChunk, SourceDocument)
            .join(SourceDocument, SourceDocument.id == KnowledgeChunk.source_document_id)
            .where(SourceDocument.bundle_id == bundle_id)
        )
        if source_document_ids is not None:
            if not source_document_ids:
                return 0
            stmt = stmt.where(KnowledgeChunk.source_document_id.in_(source_document_ids))
        rows = list(db.execute(stmt).all())
        if not rows:
            return 0

        sources: list[RequirementSource] = []
        for chunk, document in rows:
            metadata = chunk.metadata_json if isinstance(chunk.metadata_json, dict) else {}
            locator = metadata.get("locator")
            sources.append(
                RequirementSource(
                    source_document_id=document.id,
                    source_checksum=document.checksum,
                    document_version=document.version_number,
                    chunk_id=chunk.id,
                    chunk_key=chunk.chunk_key or metadata.get("chunk_key"),
                    source_locator_json={
                        "source_document_id": document.id,
                        "source_checksum": document.checksum,
                        "document_version": document.version_number,
                        "chunk_id": chunk.id,
                        "chunk_key": chunk.chunk_key or metadata.get("chunk_key"),
                        "locator": locator if isinstance(locator, dict) else None,
                    },
                    content=chunk.content,
                )
            )

        # Look up scenario-specific requirement keywords
        scenario_keywords = None
        try:
            project = db.get(Project, project_id)
            if project and project.scenario_package:
                from app.scenarios.templates import get_requirement_keywords
                scenario_keywords = get_requirement_keywords(project.scenario_package)
        except Exception:
            pass  # Fallback to default keywords

        extracted = extract_requirements(sources, project_id, scenario_keywords=scenario_keywords)
        candidates = [
            (requirement, _requirement_extraction_key(requirement))
            for requirement in extracted
            if requirement.source_document_id is not None
        ]
        if not candidates:
            return 0

        keys = [key for _, key in candidates]
        existing_keys = set(
            db.scalars(
                select(RequirementItem.extraction_key).where(
                    RequirementItem.project_id == project_id,
                    RequirementItem.extraction_key.in_(keys),
                )
            ).all()
        )

        count = 0
        for req, extraction_key in candidates:
            if extraction_key in existing_keys:
                continue
            item = RequirementItem(
                project_id=project_id,
                section_key=req.section_key,
                requirement_text=req.requirement_text,
                original_text=req.requirement_text,
                source_document_id=req.source_document_id,
                source_locator_json=req.source_locator_json,
                extraction_key=extraction_key,
                priority=req.priority,
                status="untriaged",
                extraction_confidence=req.extraction_confidence,
            )
            item.bid_profile = BidRequirementProfile(
                is_mandatory=req.priority == "high",
                coverage_status="uncovered",
                evidence_status="missing",
            )
            try:
                # The composite unique index also protects a duplicate worker
                # delivery racing this process after the preflight query.
                with db.begin_nested():
                    db.add(item)
                    db.flush()
            except IntegrityError:
                logger.info(
                    "Requirement extraction replay skipped for source document %s",
                    req.source_document_id,
                )
                continue
            count += 1
        db.commit()
        return count
    except Exception as exc:
        db.rollback()
        logger.warning("Requirement extraction failed for bundle %s: %s", bundle_id, exc)
        return 0
    finally:
        db.close()


def _requirement_extraction_key(requirement: object) -> str:
    """Hash immutable source lineage plus normalized requirement text."""
    source_document_id = getattr(requirement, "source_document_id", "") or ""
    source_checksum = getattr(requirement, "source_checksum", "") or ""
    document_version = getattr(requirement, "document_version", "") or ""
    requirement_text = getattr(requirement, "requirement_text", "") or ""
    normalized_text = " ".join(str(requirement_text).split()).casefold()
    material = "\x1f".join(
        (str(source_document_id), str(source_checksum), str(document_version), normalized_text)
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
