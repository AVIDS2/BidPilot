from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db

from .repository import list_evidence_by_project, list_chunks_by_project
from .schemas import EvidenceRead, KnowledgeChunkRead

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("", response_model=list[EvidenceRead])
def list_evidence(project_id: str, db: Session = Depends(get_db)) -> list[EvidenceRead]:
    return [
        EvidenceRead(id=e.id, project_id=e.project_id, source_document_id=e.source_document_id or "", quote_text=e.quote_text, confidence=e.confidence)
        for e in list_evidence_by_project(db, project_id)
    ]


@router.get("/chunks", response_model=list[KnowledgeChunkRead])
def list_knowledge_chunks(project_id: str, db: Session = Depends(get_db)) -> list[KnowledgeChunkRead]:
    return [
        KnowledgeChunkRead(id=c.id, project_id=c.project_id, source_document_id=c.source_document_id, chunk_index=c.chunk_index, content=c.content, metadata_json=c.metadata_json)
        for c in list_chunks_by_project(db, project_id)
    ]
