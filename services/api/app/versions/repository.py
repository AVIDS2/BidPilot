from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SectionVersion


def list_versions_by_section(db: Session, section_id: str) -> list[SectionVersion]:
    stmt = (
        select(SectionVersion)
        .where(SectionVersion.deliverable_section_id == section_id)
        .order_by(SectionVersion.version_number.desc())
    )
    return list(db.scalars(stmt).all())
