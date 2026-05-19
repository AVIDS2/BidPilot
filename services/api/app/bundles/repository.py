from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Bundle


def create_bundle(db: Session, bundle: Bundle) -> Bundle:
    db.add(bundle)
    db.commit()
    db.refresh(bundle)
    return bundle


def get_bundle(db: Session, bundle_id: str) -> Bundle | None:
    return db.get(Bundle, bundle_id)


def list_bundles_by_project(db: Session, project_id: str) -> list[Bundle]:
    stmt = select(Bundle).where(Bundle.project_id == project_id).order_by(Bundle.created_at.desc())
    return list(db.scalars(stmt).all())
