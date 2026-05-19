from sqlalchemy.orm import Session

from .repository import list_evidence_by_project
from .schemas import EvidenceRead


def list_evidence_query(db: Session, project_id: str) -> list[EvidenceRead]:
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
