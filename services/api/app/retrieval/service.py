"""Authorized API boundary for shared project evidence retrieval."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.access.service import require_project_capability
from app.auth.schemas import CurrentUser
from contracts import RetrievalResult
from contracts.retrieval_service import retrieve_project_evidence

from .metered_embedding import generate_metered_query_embedding
from .schemas import CitationRead, SearchRequest, SearchResponse, SearchResult


def _to_response(result: RetrievalResult) -> SearchResponse:
    return SearchResponse(
        project_id=result.project_id,
        results=tuple(
            SearchResult(
                chunk_id=candidate.chunk_id,
                source_document_id=candidate.source_document_id,
                content=candidate.content,
                score=candidate.final_score,
                methods=candidate.methods,
                citation=CitationRead(
                    source_document_id=candidate.locator.source_document_id,
                    chunk_index=candidate.locator.chunk_index,
                    page=candidate.locator.page,
                    heading=candidate.locator.heading,
                    table=candidate.locator.table,
                    text_anchor=candidate.locator.text_anchor,
                    validation_status=candidate.locator.validation_status,
                ),
            )
            for candidate in result.candidates
        ),
        degraded_reasons=result.degraded_reasons,
    )


def search_command(
    db: Session,
    payload: SearchRequest,
    current_user: CurrentUser,
) -> SearchResponse:
    """Authorize first, then retrieve with server-side embeddings when available."""
    access = require_project_capability(
        db,
        current_user=current_user,
        project_id=payload.project_id,
        capability="project.read",
    )
    embedding = generate_metered_query_embedding(
        current_user=current_user,
        project_id=access.project.id,
        query=payload.query,
        workload="embedding_evidence_query",
    )
    result = retrieve_project_evidence(
        db,
        project_id=access.project.id,
        raw_query=payload.query,
        profile_id=embedding.profile_id if embedding.is_success else None,
        query_embedding=embedding.vector if embedding.is_success else None,
        top_k=payload.top_k,
    )
    return _to_response(result)


def search_knowledge(
    db: Session,
    *,
    project_id: str,
    query: str,
    current_user: CurrentUser,
    top_k: int = 8,
) -> SearchResponse:
    """Internal assistant entry point using the exact same authorization path."""
    return search_command(
        db,
        SearchRequest(project_id=project_id, query=query, top_k=top_k),
        current_user,
    )


__all__ = ["search_command", "search_knowledge"]
