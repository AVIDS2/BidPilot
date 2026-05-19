from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db

from .service import list_audit_events

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events")
def get_audit_events(project_id: str, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return list_audit_events(db, project_id)
