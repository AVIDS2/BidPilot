from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .service import list_audit_events

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events")
def get_audit_events(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[dict[str, object]]:
    return list_audit_events(db, project_id, current_user)
