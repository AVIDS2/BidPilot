from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .schemas import EvidenceRead, KnowledgeChunkRead
from .service import list_evidence_query, list_knowledge_chunks_query

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("", response_model=list[EvidenceRead])
def list_evidence(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[EvidenceRead]:
    return list_evidence_query(db, project_id, current_user)


@router.get("/chunks", response_model=list[KnowledgeChunkRead])
def list_knowledge_chunks(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[KnowledgeChunkRead]:
    return list_knowledge_chunks_query(db, project_id, current_user)
