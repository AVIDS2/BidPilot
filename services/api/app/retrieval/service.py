from sqlalchemy.orm import Session

from .repository import search_chunks_by_project, search_chunks_by_vector
from .schemas import SearchRequest, SearchResult


def search_command(db: Session, payload: SearchRequest) -> list[SearchResult]:
    """Search knowledge chunks. Falls back to ILIKE text search.

    When an embedding is provided, uses pgvector cosine similarity.
    """
    if payload.embedding:
        results = search_chunks_by_vector(db, payload.project_id, payload.embedding, payload.top_k)
        return [
            SearchResult(
                chunk_id=chunk.id,
                source_document_id=chunk.source_document_id,
                content=chunk.content,
                score=1.0 - distance,  # cosine distance → similarity
            )
            for chunk, distance in results
        ]

    # Fallback: text search
    chunks = search_chunks_by_project(db, payload.project_id, payload.query, payload.top_k)
    return [
        SearchResult(
            chunk_id=c.id,
            source_document_id=c.source_document_id,
            content=c.content,
            score=1.0,
        )
        for c in chunks
    ]
