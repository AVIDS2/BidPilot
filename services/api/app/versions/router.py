from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .schemas import SectionVersionRead
from .service import list_versions_query

router = APIRouter(prefix="/versions", tags=["versions"])


@router.get("", response_model=list[SectionVersionRead])
def list_versions(
    section_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[SectionVersionRead]:
    return list_versions_query(db, section_id, current_user)
