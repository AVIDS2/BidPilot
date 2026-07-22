from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .schemas import DeliverableCreate, DeliverableRead, DeliverableSectionCreate, DeliverableSectionRead
from .service import create_deliverable_command, create_section_command, list_deliverables_query, list_sections_query

router = APIRouter(prefix="/deliverables", tags=["deliverables"])


@router.post("", response_model=DeliverableRead, status_code=status.HTTP_201_CREATED)
def create_deliverable(
    payload: DeliverableCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> DeliverableRead:
    return create_deliverable_command(db, payload, current_user)


@router.get("", response_model=list[DeliverableRead])
def list_deliverables(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[DeliverableRead]:
    return list_deliverables_query(db, project_id, current_user)


@router.post("/sections", response_model=DeliverableSectionRead, status_code=status.HTTP_201_CREATED)
def create_deliverable_section(
    payload: DeliverableSectionCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> DeliverableSectionRead:
    return create_section_command(db, payload, current_user)


@router.get("/{deliverable_id}/sections", response_model=list[DeliverableSectionRead])
def list_deliverable_sections(
    deliverable_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[DeliverableSectionRead]:
    return list_sections_query(db, deliverable_id, current_user)
