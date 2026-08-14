from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .schemas import (
    DocumentChangeImpactRead,
    DocumentChangeImpactUpdate,
    DocumentChangeSetCreate,
    DocumentChangeSetDecision,
    DocumentChangeSetRead,
)
from .service import (
    analyze_document_change_set_command,
    create_document_change_set_command,
    decide_document_change_set_command,
    list_document_change_sets_query,
    update_document_change_impact_command,
)


router = APIRouter(prefix="/changes", tags=["changes"])


@router.get("/projects/{project_id}", response_model=list[DocumentChangeSetRead])
def list_change_sets(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[DocumentChangeSetRead]:
    return list_document_change_sets_query(db, project_id=project_id, current_user=current_user)


@router.post("/projects/{project_id}", response_model=DocumentChangeSetRead, status_code=status.HTTP_201_CREATED)
def create_change_set(
    project_id: str,
    payload: DocumentChangeSetCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> DocumentChangeSetRead:
    return create_document_change_set_command(
        db,
        project_id=project_id,
        payload=payload,
        current_user=current_user,
    )


@router.post("/{change_set_id}/analyze", response_model=DocumentChangeSetRead)
def analyze_change_set(
    change_set_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> DocumentChangeSetRead:
    return analyze_document_change_set_command(db, change_set_id=change_set_id, current_user=current_user)


@router.post("/{change_set_id}/decision", response_model=DocumentChangeSetRead)
def decide_change_set(
    change_set_id: str,
    payload: DocumentChangeSetDecision,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> DocumentChangeSetRead:
    return decide_document_change_set_command(
        db,
        change_set_id=change_set_id,
        payload=payload,
        current_user=current_user,
    )


@router.patch("/{change_set_id}/impacts/{impact_id}", response_model=DocumentChangeImpactRead)
def update_impact(
    change_set_id: str,
    impact_id: str,
    payload: DocumentChangeImpactUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> DocumentChangeImpactRead:
    return update_document_change_impact_command(
        db,
        change_set_id=change_set_id,
        impact_id=impact_id,
        payload=payload,
        current_user=current_user,
    )
