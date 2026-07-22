"""Ingest execution logic: parse documents, create ParsedAssets, embed chunks, extract requirements, store, update status."""

import logging
from datetime import UTC, datetime

from app.adapters.embedding import generate_embeddings_batch, get_embedding_profile
from app.adapters.parser import parse_bundle_documents, store_chunks
from app.adapters.requirements import extract_requirements
from app.db import SessionLocal
from app.execution.embedding_capacity import (
    EmbeddingCapacityUnavailable,
    begin_official_embedding_call,
    finalize_official_embedding_call,
)
from app.models import Bundle, KnowledgeChunk, ParsedAsset, Project, RequirementItem, SourceDocument
from app.retrieval.normalization import normalize_retrieval_text
from contracts import EmbeddingOutcomeStatus
from sqlalchemy import or_

from sqlalchemy import select

logger = logging.getLogger(__name__)


def _create_parsed_assets(bundle_id: str) -> int:
    """Create ParsedAsset records for source documents that were parsed."""
    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        if bundle is None:
            return 0
        count = 0
        for doc in bundle.source_documents:
            if doc.parse_status != "parsed":
                continue
            # Check if ParsedAsset already exists
            existing = db.scalar(
                select(ParsedAsset).where(ParsedAsset.source_document_id == doc.id).limit(1)
            )
            if existing is not None:
                continue
            pa = ParsedAsset(
                source_document_id=doc.id,
                parser_name="docpilot-text-v1",
                parser_version="1.0",
                content_json={"extraction_method": "text", "mime_type": doc.mime_type},
            )
            db.add(pa)
            count += 1
        db.commit()
        return count
    finally:
        db.close()


def _embed_and_update_chunks(bundle_id: str) -> int:
    """Index only pending, failed, or profile-stale chunks without losing a good vector."""
    db = SessionLocal()
    try:
        profile = get_embedding_profile()
        if profile is None:
            # A missing server-side provider is a configuration state, not a
            # reason to overwrite a previously successful vector with null.
            return 0

        stmt = (
            select(KnowledgeChunk)
            .join(SourceDocument, SourceDocument.id == KnowledgeChunk.source_document_id)
            .where(SourceDocument.bundle_id == bundle_id)
            .where(
                or_(
                    KnowledgeChunk.embedding.is_(None),
                    KnowledgeChunk.embedding_status != "success",
                    KnowledgeChunk.embedding_profile.is_distinct_from(profile.identifier),
                )
            )
        )
        chunks = list(db.scalars(stmt).all())
        if not chunks:
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
            indexed_at = datetime.now(UTC)
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
            indexed_at = datetime.now(UTC)
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
            indexed_at = datetime.now(UTC)
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
        indexed_at = datetime.now(UTC)
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
    except Exception as exc:
        logger.warning("Embedding step failed for bundle %s: %s", bundle_id, exc)
        return 0
    finally:
        db.close()


def run_ingest(bundle_id: str) -> dict[str, str]:
    """Execute the full ingest pipeline for a bundle."""
    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        if bundle is None:
            return {"bundle_id": bundle_id, "status": "not_found"}
        bundle.ingest_status = "running"
        db.commit()
    finally:
        db.close()

    # Parse documents into chunks
    chunks = parse_bundle_documents(bundle_id)
    chunk_count = store_chunks(bundle_id, chunks)
    new_source_document_ids = {
        source_document_id
        for chunk in chunks
        if isinstance((source_document_id := chunk.metadata.get("source_document_id")), str)
        and source_document_id
    }

    # Create ParsedAsset records
    asset_count = _create_parsed_assets(bundle_id)

    # Generate embeddings for the new chunks
    embedded_count = _embed_and_update_chunks(bundle_id)

    # Extract requirements from chunk content
    req_count = _extract_and_store_requirements(bundle_id, source_document_ids=new_source_document_ids)

    # Update bundle status
    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        if bundle is not None:
            bundle.ingest_status = "ingested"
            db.commit()
    finally:
        db.close()

    return {
        "bundle_id": bundle_id,
        "status": "ingested",
        "chunks_created": str(chunk_count),
        "chunks_embedded": str(embedded_count),
        "parsed_assets_created": str(asset_count),
        "requirements_extracted": str(req_count),
    }


def run_reindex(bundle_id: str) -> dict[str, str]:
    """Refresh stale embeddings without parsing files or recreating requirements."""
    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        if bundle is None:
            return {"bundle_id": bundle_id, "status": "not_found"}
        bundle.ingest_status = "indexing"
        db.commit()
    finally:
        db.close()

    embedded_count = _embed_and_update_chunks(bundle_id)

    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        if bundle is not None:
            bundle.ingest_status = "ingested"
            db.commit()
    finally:
        db.close()

    return {
        "bundle_id": bundle_id,
        "status": "reindexed",
        "chunks_embedded": str(embedded_count),
    }


def _extract_and_store_requirements(
    bundle_id: str,
    *,
    source_document_ids: set[str] | None = None,
) -> int:
    """Extract requirements only for newly parsed source documents when provided."""
    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        if bundle is None:
            return 0
        project_id = bundle.project_id

        # Get chunk texts for requirement extraction
        stmt = (
            select(KnowledgeChunk)
            .join(SourceDocument, SourceDocument.id == KnowledgeChunk.source_document_id)
            .where(SourceDocument.bundle_id == bundle_id)
        )
        if source_document_ids is not None:
            if not source_document_ids:
                return 0
            stmt = stmt.where(KnowledgeChunk.source_document_id.in_(source_document_ids))
        chunks = list(db.scalars(stmt).all())
        if not chunks:
            return 0

        chunk_texts = [c.content for c in chunks]

        # Look up scenario-specific requirement keywords
        scenario_keywords = None
        try:
            project = db.get(Project, project_id)
            if project and project.scenario_package:
                from app.scenarios.templates import get_requirement_keywords
                scenario_keywords = get_requirement_keywords(project.scenario_package)
        except Exception:
            pass  # Fallback to default keywords

        extracted = extract_requirements(chunk_texts, project_id, scenario_keywords=scenario_keywords)

        count = 0
        for req in extracted:
            ri = RequirementItem(
                project_id=project_id,
                section_key=req.section_key,
                requirement_text=req.requirement_text,
                priority=req.priority,
            )
            db.add(ri)
            count += 1
        db.commit()
        return count
    except Exception as exc:
        logger.warning("Requirement extraction failed for bundle %s: %s", bundle_id, exc)
        return 0
    finally:
        db.close()
