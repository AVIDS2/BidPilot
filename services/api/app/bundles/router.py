from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db

from .schemas import BundleCreate, BundleRead
from .service import list_bundles_query, reingest_bundle_command, register_bundle_command

router = APIRouter(prefix="/bundles", tags=["bundles"])


@router.post("", response_model=BundleRead, status_code=status.HTTP_201_CREATED)
def register_bundle(payload: BundleCreate, db: Session = Depends(get_db)) -> BundleRead:
    return register_bundle_command(db, payload)


@router.get("", response_model=list[BundleRead])
def list_bundles(project_id: str, db: Session = Depends(get_db)) -> list[BundleRead]:
    return list_bundles_query(db, project_id)


@router.post("/{bundle_id}/reingest", response_model=BundleRead)
def reingest_bundle(bundle_id: str, db: Session = Depends(get_db)) -> BundleRead:
    return reingest_bundle_command(db, bundle_id)
