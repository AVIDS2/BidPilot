from sqlalchemy.orm import Session

from app.access.service import require_deliverable_capability, require_project_capability
from app.auth.schemas import CurrentUser
from app.models import Deliverable, DeliverableSection

from .repository import create_deliverable, create_section, list_deliverables_by_project, list_sections_by_deliverable
from .schemas import DeliverableCreate, DeliverableRead, DeliverableSectionCreate, DeliverableSectionRead


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
    return DeliverableRead(id=d.id, project_id=d.project_id, type=d.type, title=d.title, status=d.status, export_status=d.export_status)


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
    return [DeliverableRead(id=d.id, project_id=d.project_id, type=d.type, title=d.title, status=d.status, export_status=d.export_status) for d in deliverables]


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
    s = DeliverableSection(deliverable_id=payload.deliverable_id, section_key=payload.section_key, title=payload.title)
    s = create_section(db, s)
    return DeliverableSectionRead(id=s.id, deliverable_id=s.deliverable_id, section_key=s.section_key, title=s.title, status=s.status)


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
    return [DeliverableSectionRead(id=s.id, deliverable_id=s.deliverable_id, section_key=s.section_key, title=s.title, status=s.status) for s in sections]
