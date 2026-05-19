from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RequirementItem


def create_requirement(db: Session, item: RequirementItem) -> RequirementItem:
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_requirements_by_project(db: Session, project_id: str) -> list[RequirementItem]:
    stmt = (
        select(RequirementItem)
        .where(RequirementItem.project_id == project_id)
        .order_by(RequirementItem.section_key, RequirementItem.priority)
    )
    return list(db.scalars(stmt).all())


def get_requirement(db: Session, requirement_id: str) -> RequirementItem | None:
    return db.get(RequirementItem, requirement_id)


def update_requirement(db: Session, item: RequirementItem) -> RequirementItem:
    db.commit()
    db.refresh(item)
    return item
