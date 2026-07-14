from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import BidRequirementProfile, Project, ReadinessPack, RequirementItem


def get_project_for_org(
    db: Session,
    project_id: str,
    org_id: str,
    *,
    for_update: bool = False,
) -> Project | None:
    stmt = select(Project).where(Project.id == project_id, Project.org_id == org_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def list_project_requirements(db: Session, project_id: str) -> list[RequirementItem]:
    stmt = (
        select(RequirementItem)
        .options(selectinload(RequirementItem.bid_profile))
        .where(RequirementItem.project_id == project_id)
        .order_by(RequirementItem.section_key, RequirementItem.id)
    )
    return list(db.scalars(stmt).all())


def next_pack_version(db: Session, project_id: str) -> int:
    latest = db.scalar(
        select(func.max(ReadinessPack.version_number)).where(
            ReadinessPack.project_id == project_id
        )
    )
    return int(latest or 0) + 1


def get_pack_for_org(db: Session, pack_id: str, org_id: str) -> ReadinessPack | None:
    stmt = (
        select(ReadinessPack)
        .join(Project, Project.id == ReadinessPack.project_id)
        .where(ReadinessPack.id == pack_id, Project.org_id == org_id)
    )
    return db.scalar(stmt)

