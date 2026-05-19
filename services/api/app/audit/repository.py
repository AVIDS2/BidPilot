from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent


def create_event(db: Session, event: AuditEvent) -> AuditEvent:
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_events_by_project(db: Session, project_id: str) -> list[AuditEvent]:
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.project_id == project_id)
        .order_by(AuditEvent.created_at.desc())
    )
    return list(db.scalars(stmt).all())
