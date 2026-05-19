from sqlalchemy.orm import Session

from app.models import Deliverable, DeliverableSection

from .repository import create_deliverable, create_section, list_deliverables_by_project, list_sections_by_deliverable
from .schemas import DeliverableCreate, DeliverableRead, DeliverableSectionCreate, DeliverableSectionRead


def create_deliverable_command(db: Session, payload: DeliverableCreate) -> DeliverableRead:
    d = Deliverable(project_id=payload.project_id, type=payload.type, title=payload.title)
    d = create_deliverable(db, d)
    return DeliverableRead(id=d.id, project_id=d.project_id, type=d.type, title=d.title, status=d.status, export_status=d.export_status)


def list_deliverables_query(db: Session, project_id: str) -> list[DeliverableRead]:
    deliverables = list_deliverables_by_project(db, project_id)
    return [DeliverableRead(id=d.id, project_id=d.project_id, type=d.type, title=d.title, status=d.status, export_status=d.export_status) for d in deliverables]


def create_section_command(db: Session, payload: DeliverableSectionCreate) -> DeliverableSectionRead:
    s = DeliverableSection(deliverable_id=payload.deliverable_id, section_key=payload.section_key, title=payload.title)
    s = create_section(db, s)
    return DeliverableSectionRead(id=s.id, deliverable_id=s.deliverable_id, section_key=s.section_key, title=s.title, status=s.status)


def list_sections_query(db: Session, deliverable_id: str) -> list[DeliverableSectionRead]:
    sections = list_sections_by_deliverable(db, deliverable_id)
    return [DeliverableSectionRead(id=s.id, deliverable_id=s.deliverable_id, section_key=s.section_key, title=s.title, status=s.status) for s in sections]
