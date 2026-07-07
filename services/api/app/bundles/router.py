from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db
from app.usage.service import UsageLimitExceeded

from .schemas import BundleCreate, BundleRead
from .service import list_bundles_query, reingest_bundle_command, register_bundle_command

router = APIRouter(prefix="/bundles", tags=["bundles"])


@router.post("", response_model=BundleRead, status_code=status.HTTP_201_CREATED)
def register_bundle(
    payload: BundleCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> BundleRead:
    try:
        return register_bundle_command(db, payload, current_user)
    except UsageLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.get("", response_model=list[BundleRead])
def list_bundles(project_id: str, db: Session = Depends(get_db)) -> list[BundleRead]:
    return list_bundles_query(db, project_id)


@router.post("/{bundle_id}/reingest", response_model=BundleRead)
def reingest_bundle(
    bundle_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> BundleRead:
    try:
        return reingest_bundle_command(db, bundle_id, current_user)
    except UsageLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
