from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Evidence, KnowledgeChunk


def list_evidence_by_project(db: Session, project_id: str) -> list[Evidence]:
    stmt = (
        select(Evidence)
        .where(Evidence.project_id == project_id)
        .order_by(Evidence.confidence.desc().nulls_last())
    )
    return list(db.scalars(stmt).all())


def list_chunks_by_project(db: Session, project_id: str) -> list[KnowledgeChunk]:
    stmt = (
        select(KnowledgeChunk)
        .where(KnowledgeChunk.project_id == project_id)
        .order_by(KnowledgeChunk.chunk_index)
    )
    return list(db.scalars(stmt).all())
