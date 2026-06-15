from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .service import usage_quota_dict

router = APIRouter(prefix="/usage", tags=["usage"], dependencies=[Depends(require_auth)])


@router.get("/quota")
def read_usage_quota(
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    return {"data": usage_quota_dict(db, current_user.id)}
