"""Knowledge retriever node: find relevant chunks via pgvector similarity.

Wraps the existing retrieval logic from ``app.execution.drafting`` but
returns actual cosine distance scores instead of a rank-based heuristic.
"""

from __future__ import annotations

import logging
import time

from app.adapters.embedding import generate_embedding
from app.db import SessionLocal
from app.models import KnowledgeChunk
from sqlalchemy import literal_column, select

from ..state import BidPilotState, EvidenceChunk
from ._history import record_agent_call

logger = logging.getLogger(__name__)

_TOP_K = 5


def knowledge_retriever_node(state: BidPilotState) -> dict:
    """LangGraph node: retrieve evidence chunks for a section.

    Generates an embedding for the section key, then uses pgvector
    ``cosine_distance`` to find the most relevant ``KnowledgeChunk`` rows.
    Falls back to ILIKE text search when embeddings are unavailable.

    Each ``EvidenceChunk`` carries its actual ``cosine_distance`` value so
    downstream nodes (quality reviewer, persist) can use real similarity
    scores rather than a descending-rank heuristic.

    Returns:
        Partial state update with ``evidence_chunks`` list,
        ``evidence_retrieved`` flag, and ``agent_history`` record.
    """
    start = time.monotonic()
    project_id: str = state["project_id"]
    section_key: str = state["section_key"]

    query_embedding = generate_embedding(section_key)
    chunks: list[EvidenceChunk] = []
    retrieval_method = "unknown"

    db = SessionLocal()
    try:
        # ── Strategy 1: pgvector cosine similarity ────────────────────
        if query_embedding.model != "stub":
            # Performance: fetch row + distance in a single query to avoid
            # N+1 queries (previously each row triggered an extra distance calc).
            distance_expr = KnowledgeChunk.embedding.cosine_distance(
                query_embedding.embedding
            )
            stmt = (
                select(KnowledgeChunk, distance_expr.label("distance"))
                .where(
                    KnowledgeChunk.project_id == project_id,
                    KnowledgeChunk.embedding.isnot(None),
                )
                .order_by(literal_column("distance"))
                .limit(_TOP_K)
            )
            rows = db.execute(stmt).all()
            if rows:
                for row, distance in rows:
                    chunks.append(
                        EvidenceChunk(
                            chunk_id=row.id,
                            source_document_id=row.source_document_id,
                            content=row.content[:500],
                            cosine_distance=float(distance),
                            chunk_index=row.chunk_index,
                        )
                    )
                retrieval_method = "pgvector_cosine"
                duration_ms = int((time.monotonic() - start) * 1000)
                history = record_agent_call(
                    agent="knowledge_retriever",
                    action="retrieve_evidence",
                    input_summary=f"project_id={project_id}, section={section_key}, method={retrieval_method}",
                    output_summary=f"evidence_chunks[{len(chunks)}], avg_distance={sum(c['cosine_distance'] for c in chunks) / len(chunks):.4f}",
                    duration_ms=duration_ms,
                    success=True,
                )
                return {
                    "evidence_chunks": chunks,
                    "evidence_retrieved": True,
                    "agent_history": history,
                }

        # ── Strategy 2: ILIKE text search ─────────────────────────────
        pattern = f"%{section_key.replace('-', '%')}%"
        stmt = (
            select(KnowledgeChunk)
            .where(
                KnowledgeChunk.project_id == project_id,
                KnowledgeChunk.content.ilike(pattern),
            )
            .limit(_TOP_K)
        )
        rows = list(db.scalars(stmt).all())
        if rows:
            for row in rows:
                chunks.append(
                    EvidenceChunk(
                        chunk_id=row.id,
                        source_document_id=row.source_document_id,
                        content=row.content[:500],
                        cosine_distance=1.0,  # unknown distance
                        chunk_index=row.chunk_index,
                    )
                )
            retrieval_method = "ilike_text"
            duration_ms = int((time.monotonic() - start) * 1000)
            history = record_agent_call(
                agent="knowledge_retriever",
                action="retrieve_evidence",
                input_summary=f"project_id={project_id}, section={section_key}, method={retrieval_method}",
                output_summary=f"evidence_chunks[{len(chunks)}]",
                duration_ms=duration_ms,
                success=True,
            )
            return {
                "evidence_chunks": chunks,
                "evidence_retrieved": True,
                "agent_history": history,
            }

        # ── Strategy 3: any chunks in the project (last resort) ───────
        stmt = (
            select(KnowledgeChunk)
            .where(KnowledgeChunk.project_id == project_id)
            .limit(_TOP_K)
        )
        rows = list(db.scalars(stmt).all())
        for row in rows:
            chunks.append(
                EvidenceChunk(
                    chunk_id=row.id,
                    source_document_id=row.source_document_id,
                    content=row.content[:500],
                    cosine_distance=1.0,
                    chunk_index=row.chunk_index,
                )
            )
        retrieval_method = "fallback_all"

        if not chunks:
            logger.warning(
                "No knowledge chunks found for project %s, section %s",
                project_id,
                section_key,
            )

        duration_ms = int((time.monotonic() - start) * 1000)
        history = record_agent_call(
            agent="knowledge_retriever",
            action="retrieve_evidence",
            input_summary=f"project_id={project_id}, section={section_key}, method={retrieval_method}",
            output_summary=f"evidence_chunks[{len(chunks)}]",
            duration_ms=duration_ms,
            success=True,
        )

        return {
            "evidence_chunks": chunks,
            "evidence_retrieved": True,
            "agent_history": history,
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.exception(
            "knowledge_retriever_node failed for project %s, section %s",
            project_id,
            section_key,
        )

        history = record_agent_call(
            agent="knowledge_retriever",
            action="retrieve_evidence",
            input_summary=f"project_id={project_id}, section={section_key}",
            output_summary=f"ERROR: {exc}",
            duration_ms=duration_ms,
            success=False,
            error=str(exc),
        )

        return {
            "evidence_chunks": [],
            "evidence_retrieved": True,
            "error": f"knowledge_retriever: {exc}",
            "agent_history": history,
        }
    finally:
        db.close()
