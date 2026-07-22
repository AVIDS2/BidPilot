from sqlalchemy.orm import Session

from app.access.service import require_project_capability
from app.auth.schemas import CurrentUser

from .repository import list_chunks_by_project, list_evidence_by_project
from .schemas import EvidenceRead, KnowledgeChunkRead


def list_evidence_query(
    db: Session,
    project_id: str,
    current_user: CurrentUser,
) -> list[EvidenceRead]:
    require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.read",
    )
    items = list_evidence_by_project(db, project_id)
    return [
        EvidenceRead(
            id=e.id,
            project_id=e.project_id,
            source_document_id=e.source_document_id,
            quote_text=e.quote_text,
            confidence=e.confidence,
        )
        for e in items
    ]


def list_knowledge_chunks_query(
    db: Session,
    project_id: str,
    current_user: CurrentUser,
) -> list[KnowledgeChunkRead]:
    require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.read",
    )
    return [
        KnowledgeChunkRead(
            id=chunk.id,
            project_id=chunk.project_id,
            source_document_id=chunk.source_document_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            metadata_json=chunk.metadata_json,
        )
        for chunk in list_chunks_by_project(db, project_id)
    ]
