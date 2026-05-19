from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

from app.models import KnowledgeChunk


def search_chunks_by_project(db: Session, project_id: str, query: str, top_k: int = 10) -> list[KnowledgeChunk]:
    """Full-text search on knowledge chunks. Uses ILIKE fallback.

    When embeddings are populated, use pgvector cosine similarity instead.
    """
    stmt = (
        select(KnowledgeChunk)
        .where(
            KnowledgeChunk.project_id == project_id,
            KnowledgeChunk.content.ilike(f"%{query}%"),
        )
        .order_by(KnowledgeChunk.chunk_index)
        .limit(top_k)
    )
    return list(db.scalars(stmt).all())


def search_chunks_by_vector(db: Session, project_id: str, embedding: list[float], top_k: int = 10) -> list[tuple[KnowledgeChunk, float]]:
    """Search knowledge chunks using pgvector cosine similarity.

    Returns list of (chunk, distance) tuples. Lower distance = more similar.
    """
    stmt = (
        select(
            KnowledgeChunk,
            KnowledgeChunk.embedding.cosine_distance(embedding).label("distance"),
        )
        .where(
            KnowledgeChunk.project_id == project_id,
            KnowledgeChunk.embedding.isnot(None),
        )
        .order_by("distance")
        .limit(top_k)
    )
    rows = db.execute(stmt).all()
    return [(row[0], row[1]) for row in rows]


def count_chunks_by_project(db: Session, project_id: str) -> int:
    return db.scalar(
        select(func.count()).select_from(KnowledgeChunk).where(KnowledgeChunk.project_id == project_id)
    ) or 0
