from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.access.service import require_deliverable_capability, require_project_capability
from app.auth.schemas import CurrentUser
from app.models import Deliverable, DeliverableSection

from .repository import (
    create_deliverable,
    create_section,
    delete_section,
    get_section,
    list_deliverables_by_project,
    list_sections_by_deliverable,
    next_sort_order,
    reorder_sections,
    section_has_versions,
    update_section,
)
from .schemas import (
    DeliverableCreate,
    DeliverableRead,
    DeliverableSectionCreate,
    DeliverableSectionRead,
    DeliverableSectionReorder,
    DeliverableSectionUpdate,
)


def _section_read(section: DeliverableSection) -> DeliverableSectionRead:
    return DeliverableSectionRead(
        id=section.id,
        deliverable_id=section.deliverable_id,
        section_key=section.section_key,
        title=section.title,
        status=section.status,
        approved_version_id=section.approved_version_id,
        sort_order=int(getattr(section, "sort_order", 0) or 0),
    )


def create_deliverable_command(
    db: Session,
    payload: DeliverableCreate,
    current_user: CurrentUser,
) -> DeliverableRead:
    require_project_capability(
        db,
        current_user=current_user,
        project_id=payload.project_id,
        capability="project.manage",
    )
    d = Deliverable(project_id=payload.project_id, type=payload.type, title=payload.title)
    d = create_deliverable(db, d)
    return DeliverableRead(
        id=d.id,
        project_id=d.project_id,
        type=d.type,
        title=d.title,
        status=d.status,
        export_status=d.export_status,
    )


def list_deliverables_query(
    db: Session,
    project_id: str,
    current_user: CurrentUser,
) -> list[DeliverableRead]:
    require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.read",
    )
    deliverables = list_deliverables_by_project(db, project_id)
    return [
        DeliverableRead(
            id=d.id,
            project_id=d.project_id,
            type=d.type,
            title=d.title,
            status=d.status,
            export_status=d.export_status,
        )
        for d in deliverables
    ]


def create_section_command(
    db: Session,
    payload: DeliverableSectionCreate,
    current_user: CurrentUser,
) -> DeliverableSectionRead:
    require_deliverable_capability(
        db,
        current_user=current_user,
        deliverable_id=payload.deliverable_id,
        capability="project.manage",
    )
    existing = list_sections_by_deliverable(db, payload.deliverable_id)
    if any(section.section_key == payload.section_key for section in existing):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "section_key_exists", "section_key": payload.section_key},
        )
    sort_order = (
        payload.sort_order
        if payload.sort_order is not None
        else next_sort_order(db, payload.deliverable_id)
    )
    s = DeliverableSection(
        deliverable_id=payload.deliverable_id,
        section_key=payload.section_key,
        title=payload.title,
        sort_order=sort_order,
    )
    s = create_section(db, s)
    return _section_read(s)


def list_sections_query(
    db: Session,
    deliverable_id: str,
    current_user: CurrentUser,
) -> list[DeliverableSectionRead]:
    require_deliverable_capability(
        db,
        current_user=current_user,
        deliverable_id=deliverable_id,
        capability="project.read",
    )
    sections = list_sections_by_deliverable(db, deliverable_id)
    return [_section_read(s) for s in sections]


def update_section_command(
    db: Session,
    section_id: str,
    payload: DeliverableSectionUpdate,
    current_user: CurrentUser,
) -> DeliverableSectionRead:
    section = get_section(db, section_id)
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="section_not_found")
    require_deliverable_capability(
        db,
        current_user=current_user,
        deliverable_id=section.deliverable_id,
        capability="project.manage",
    )
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="title_required")
        section.title = title
    if payload.section_key is not None:
        key = payload.section_key.strip()
        if not key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="section_key_required")
        siblings = list_sections_by_deliverable(db, section.deliverable_id)
        if any(s.section_key == key and s.id != section.id for s in siblings):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "section_key_exists", "section_key": key},
            )
        section.section_key = key
    if payload.sort_order is not None:
        section.sort_order = payload.sort_order
    section = update_section(db, section)
    return _section_read(section)


def reorder_sections_command(
    db: Session,
    deliverable_id: str,
    payload: DeliverableSectionReorder,
    current_user: CurrentUser,
) -> list[DeliverableSectionRead]:
    require_deliverable_capability(
        db,
        current_user=current_user,
        deliverable_id=deliverable_id,
        capability="project.manage",
    )
    try:
        sections = reorder_sections(db, deliverable_id, payload.section_ids)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_section_order", "message": str(exc)},
        ) from exc
    return [_section_read(s) for s in sections]


def delete_section_command(
    db: Session,
    section_id: str,
    current_user: CurrentUser,
    *,
    force: bool = False,
) -> dict:
    section = get_section(db, section_id)
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="section_not_found")
    require_deliverable_capability(
        db,
        current_user=current_user,
        deliverable_id=section.deliverable_id,
        capability="project.manage",
    )
    if section_has_versions(db, section.id) and not force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "section_has_content",
                "message": "章节已有正文版本，删除需 force=true。",
            },
        )
    delete_section(db, section)
    return {"deleted": True, "section_id": section_id}
