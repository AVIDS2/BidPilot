"""Ingest execution logic: parse documents, create ParsedAssets, embed chunks, extract requirements, store, update status."""

import logging

from app.adapters.embedding import generate_embeddings_batch
from app.adapters.parser import parse_bundle_documents, store_chunks
from app.adapters.requirements import extract_requirements
from app.db import SessionLocal
from app.models import Bundle, KnowledgeChunk, ParsedAsset, Project, RequirementItem, SourceDocument

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
    """Generate embeddings for all chunks in a bundle and update DB rows."""
    db = SessionLocal()
    try:
        stmt = (
            select(KnowledgeChunk)
            .join(KnowledgeChunk.source_document)
            .where(KnowledgeChunk.source_document.has(bundle_id=bundle_id))
            .where(KnowledgeChunk.embedding.is_(None))
        )
        chunks = list(db.scalars(stmt).all())
        if not chunks:
            return 0

        texts = [c.content for c in chunks]
        results = generate_embeddings_batch(texts)

        for chunk, emb_result in zip(chunks, results):
            chunk.embedding = emb_result.embedding
        db.commit()
        return len(chunks)
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

    # Create ParsedAsset records
    asset_count = _create_parsed_assets(bundle_id)

    # Generate embeddings for the new chunks
    embedded_count = _embed_and_update_chunks(bundle_id)

    # Extract requirements from chunk content
    req_count = _extract_and_store_requirements(bundle_id)

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


def _extract_and_store_requirements(bundle_id: str) -> int:
    """Extract requirements from chunks and store as RequirementItem rows."""
    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        if bundle is None:
            return 0
        project_id = bundle.project_id

        # Get chunk texts for requirement extraction
        stmt = (
            select(KnowledgeChunk)
            .join(KnowledgeChunk.source_document)
            .where(KnowledgeChunk.source_document.has(bundle_id=bundle_id))
        )
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
