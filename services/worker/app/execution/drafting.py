"""Drafting execution logic: retrieve evidence via pgvector, call LLM, write section version, link evidence."""

import logging
from datetime import UTC, datetime

from app.adapters.embedding import generate_embedding
from app.adapters.llm import draft_section as draft_section_openai
from app.adapters.anthropic_llm import draft_section as draft_section_anthropic
from app.db import SessionLocal
from app.provider_registry import get_provider_by_id
from app.models import (
    DeliverableSection,
    Evidence,
    ExecutionRun,
    KnowledgeChunk,
    Project,
    SectionVersion,
)
from sqlalchemy import select

logger = logging.getLogger(__name__)


def _retrieve_evidence(project_id: str, section_key: str, top_k: int = 5) -> list[KnowledgeChunk]:
    """Retrieve relevant knowledge chunks for a section.

    Uses pgvector cosine similarity when embeddings are available,
    falls back to ILIKE text search otherwise.
    Returns chunk objects (with id, content, source_document_id) for evidence linking.
    """
    # Generate embedding for the section key as query
    query_embedding = generate_embedding(section_key)

    db = SessionLocal()
    try:
        # Try vector search first when we have a real embedding
        if query_embedding.model != "stub":
            stmt = (
                select(KnowledgeChunk)
                .where(
                    KnowledgeChunk.project_id == project_id,
                    KnowledgeChunk.embedding.isnot(None),
                )
                .order_by(KnowledgeChunk.embedding.cosine_distance(query_embedding.embedding))
                .limit(top_k)
            )
            chunks = list(db.scalars(stmt).all())
            if chunks:
                return chunks

        # Fallback: text search
        stmt = (
            select(KnowledgeChunk)
            .where(
                KnowledgeChunk.project_id == project_id,
                KnowledgeChunk.content.ilike(f"%{section_key.replace('-', '%')}%"),
            )
            .limit(top_k)
        )
        chunks = list(db.scalars(stmt).all())
        if chunks:
            return chunks

        # Final fallback: any chunks in project
        stmt = (
            select(KnowledgeChunk)
            .where(KnowledgeChunk.project_id == project_id)
            .limit(top_k)
        )
        chunks = list(db.scalars(stmt).all())
        return chunks
    finally:
        db.close()


def _link_evidence(db, project_id: str, section_version_id: str, chunks: list[KnowledgeChunk]) -> None:
    """Create Evidence records linking each chunk to the section version."""
    for i, chunk in enumerate(chunks):
        ev = Evidence(
            project_id=project_id,
            section_version_id=section_version_id,
            source_document_id=chunk.source_document_id,
            chunk_id=chunk.id,
            quote_text=chunk.content[:500],
            locator_json={"chunk_index": chunk.chunk_index},
            confidence=1.0 - (i * 0.1),  # Simple descending confidence
        )
        db.add(ev)


def run_draft(run_id: str, project_id: str, section_key: str, review_feedback: str | None = None, provider_config_id: str | None = None) -> dict[str, str]:
    """Execute the full drafting pipeline for a section.

    Args:
        provider_config_id: Optional user provider config ID. When provided,
                            resolves the provider from the DB and uses its
                            credentials instead of env-var defaults.
    """
    db = SessionLocal()
    try:
        run = db.get(ExecutionRun, run_id)
        if run is None:
            return {"run_id": run_id, "status": "not_found"}
        run.status = "running"
        run.started_at = datetime.now(UTC)
        db.commit()
    finally:
        db.close()

    # Retrieve evidence
    chunks = _retrieve_evidence(project_id, section_key)
    evidence_texts = [c.content for c in chunks]

    # Look up scenario-specific system prompt
    system_prompt = None
    try:
        db2 = SessionLocal()
        project = db2.get(Project, project_id)
        if project and project.scenario_package:
            from app.scenarios.templates import get_drafting_prompt
            system_prompt = get_drafting_prompt(project.scenario_package)
        db2.close()
    except Exception:
        pass  # Fallback to default prompt

    # Call LLM adapter with optional user-provided provider config
    provider_params = None
    if provider_config_id:
        provider_params = get_provider_by_id(provider_config_id)

    provider_config_dict = None
    if provider_params:
        provider_config_dict = {
            "api_key": provider_params.api_key,
            "api_url": provider_params.api_url,
            "model": provider_params.model,
        }

    if provider_params and provider_params.provider_type == "anthropic":
        result = draft_section_anthropic(
            section_key, evidence_texts, project_id,
            review_feedback=review_feedback,
            system_prompt=system_prompt,
            provider_config=provider_config_dict,
        )
    else:
        # Default to OpenAI-compatible (also handles fallback when no provider_config)
        result = draft_section_openai(
            section_key, evidence_texts, project_id,
            review_feedback=review_feedback,
            system_prompt=system_prompt,
            provider_config=provider_config_dict,
        )

    # Write section version if a matching section exists
    section_version_id = None
    db = SessionLocal()
    try:
        section = db.scalar(
            select(DeliverableSection).where(DeliverableSection.section_key == section_key).limit(1)
        )
        if section is not None:
            # Determine next version number
            existing = db.scalar(
                select(SectionVersion)
                .where(SectionVersion.deliverable_section_id == section.id)
                .order_by(SectionVersion.version_number.desc())
                .limit(1)
            )
            next_version = (existing.version_number + 1) if existing else 1
            sv = SectionVersion(
                deliverable_section_id=section.id,
                version_number=next_version,
                content_markdown=result.content_markdown,
                created_by_actor="ai",
                generation_run_id=run_id,
            )
            db.add(sv)
            db.flush()
            section_version_id = sv.id

            # Link evidence to this section version
            if chunks:
                _link_evidence(db, project_id, section_version_id, chunks)

            # If no evidence found, add a missing-evidence marker
            if not chunks:
                ev = Evidence(
                    project_id=project_id,
                    section_version_id=section_version_id,
                    quote_text="[NO EVIDENCE FOUND] No relevant knowledge chunks were retrieved for this section.",
                    locator_json={"marker": "missing-evidence"},
                    confidence=0.0,
                )
                db.add(ev)

            db.commit()
    finally:
        db.close()

    # Update run status
    db = SessionLocal()
    try:
        run = db.get(ExecutionRun, run_id)
        if run is not None:
            run.status = "succeeded"
            run.finished_at = datetime.now(UTC)
            run.output_json = {
                "section_key": section_key,
                "model_used": result.model_used,
                "evidence_count": len(chunks),
                "section_version_id": section_version_id,
            }
            db.commit()
    finally:
        db.close()

    return {"run_id": run_id, "status": "succeeded", "model_used": result.model_used}
