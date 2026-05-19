from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Deliverable, DeliverableSection


def create_deliverable(db: Session, deliverable: Deliverable) -> Deliverable:
    db.add(deliverable)
    db.commit()
    db.refresh(deliverable)
    return deliverable


def get_deliverable(db: Session, deliverable_id: str) -> Deliverable | None:
    return db.get(Deliverable, deliverable_id)


def list_deliverables_by_project(db: Session, project_id: str) -> list[Deliverable]:
    stmt = select(Deliverable).where(Deliverable.project_id == project_id).order_by(Deliverable.title)
    return list(db.scalars(stmt).all())


def create_section(db: Session, section: DeliverableSection) -> DeliverableSection:
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


def list_sections_by_deliverable(db: Session, deliverable_id: str) -> list[DeliverableSection]:
    stmt = select(DeliverableSection).where(DeliverableSection.deliverable_id == deliverable_id).order_by(DeliverableSection.section_key)
    return list(db.scalars(stmt).all())
