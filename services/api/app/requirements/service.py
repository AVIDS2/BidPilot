from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.audit.service import record_audit_event
from app.models import RequirementItem

from .repository import create_requirement, get_requirement, list_requirements_by_project, update_requirement
from .schemas import RequirementItemCreate, RequirementItemRead, RequirementItemUpdate


def create_requirement_command(db: Session, payload: RequirementItemCreate) -> RequirementItemRead:
    item = RequirementItem(
        project_id=payload.project_id,
        section_key=payload.section_key,
        requirement_text=payload.requirement_text,
        priority=payload.priority,
    )
    item = create_requirement(db, item)
    return RequirementItemRead(
        id=item.id,
        project_id=item.project_id,
        section_key=item.section_key,
        requirement_text=item.requirement_text,
        priority=item.priority,
        status=item.status,
    )


def list_requirements_query(db: Session, project_id: str) -> list[RequirementItemRead]:
    items = list_requirements_by_project(db, project_id)
    return [
        RequirementItemRead(
            id=i.id,
            project_id=i.project_id,
            section_key=i.section_key,
            requirement_text=i.requirement_text,
            priority=i.priority,
            status=i.status,
        )
        for i in items
    ]


def update_requirement_command(db: Session, requirement_id: str, payload: RequirementItemUpdate) -> RequirementItemRead:
    item = get_requirement(db, requirement_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Requirement not found")

    if payload.requirement_text is not None:
        item.requirement_text = payload.requirement_text
    if payload.priority is not None:
        item.priority = payload.priority
    if payload.section_key is not None:
        item.section_key = payload.section_key
    if payload.status is not None:
        item.status = payload.status

    item = update_requirement(db, item)
    record_audit_event(db, project_id=item.project_id, event_type="requirement.updated", payload={"requirement_id": item.id})
    db.commit()

    return RequirementItemRead(
        id=item.id,
        project_id=item.project_id,
        section_key=item.section_key,
        requirement_text=item.requirement_text,
        priority=item.priority,
        status=item.status,
    )
