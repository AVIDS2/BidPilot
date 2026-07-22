"""Compatibility helpers for non-ranking retrieval repository operations.

Ranking queries live exclusively in ``contracts.retrieval_repository`` so API,
worker, drafting, and graph execution cannot drift into different semantics.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import KnowledgeChunk


def count_chunks_by_project(db: Session, project_id: str) -> int:
    return db.scalar(
        select(func.count()).select_from(KnowledgeChunk).where(KnowledgeChunk.project_id == project_id)
    ) or 0


__all__ = ["count_chunks_by_project"]
