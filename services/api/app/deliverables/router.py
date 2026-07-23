from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .schemas import (
    DeliverableCreate,
    DeliverableRead,
    DeliverableSectionCreate,
    DeliverableSectionRead,
    DeliverableSectionReorder,
    DeliverableSectionUpdate,
)
from .service import (
    create_deliverable_command,
    create_section_command,
    delete_section_command,
    list_deliverables_query,
    list_sections_query,
    reorder_sections_command,
    update_section_command,
)

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


@router.patch("/sections/{section_id}", response_model=DeliverableSectionRead)
def update_deliverable_section(
    section_id: str,
    payload: DeliverableSectionUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> DeliverableSectionRead:
    return update_section_command(db, section_id, payload, current_user)


@router.put(
    "/{deliverable_id}/sections/reorder",
    response_model=list[DeliverableSectionRead],
)
def reorder_deliverable_sections(
    deliverable_id: str,
    payload: DeliverableSectionReorder,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[DeliverableSectionRead]:
    return reorder_sections_command(db, deliverable_id, payload, current_user)


@router.delete("/sections/{section_id}")
def delete_deliverable_section(
    section_id: str,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> dict:
    return delete_section_command(db, section_id, current_user, force=force)
