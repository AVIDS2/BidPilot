from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Deliverable, DeliverableSection, SectionVersion


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


def get_section(db: Session, section_id: str) -> DeliverableSection | None:
    return db.get(DeliverableSection, section_id)


def next_sort_order(db: Session, deliverable_id: str) -> int:
    current = db.scalar(
        select(func.max(DeliverableSection.sort_order)).where(
            DeliverableSection.deliverable_id == deliverable_id
        )
    )
    return int(current or 0) + 1


def list_sections_by_deliverable(db: Session, deliverable_id: str) -> list[DeliverableSection]:
    stmt = (
        select(DeliverableSection)
        .where(DeliverableSection.deliverable_id == deliverable_id)
        .order_by(DeliverableSection.sort_order.asc(), DeliverableSection.section_key.asc())
    )
    return list(db.scalars(stmt).all())


def update_section(db: Session, section: DeliverableSection) -> DeliverableSection:
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


def reorder_sections(
    db: Session,
    deliverable_id: str,
    section_ids: list[str],
) -> list[DeliverableSection]:
    sections = {
        section.id: section
        for section in list_sections_by_deliverable(db, deliverable_id)
    }
    if set(section_ids) != set(sections):
        missing = set(sections) - set(section_ids)
        extra = set(section_ids) - set(sections)
        raise ValueError(
            f"section_ids must include every section exactly once "
            f"(missing={sorted(missing)}, extra={sorted(extra)})"
        )
    for index, section_id in enumerate(section_ids):
        sections[section_id].sort_order = index
        db.add(sections[section_id])
    db.commit()
    return list_sections_by_deliverable(db, deliverable_id)


def section_has_versions(db: Session, section_id: str) -> bool:
    return (
        db.scalar(
            select(SectionVersion.id)
            .where(SectionVersion.deliverable_section_id == section_id)
            .limit(1)
        )
        is not None
    )


def delete_section(db: Session, section: DeliverableSection) -> None:
    db.delete(section)
    db.commit()
