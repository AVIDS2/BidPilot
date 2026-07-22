from sqlalchemy.orm import Session

from app.access.service import require_project_capability
from app.auth.schemas import CurrentUser
from app.models import AuditEvent

from .repository import list_events_by_project


def record_audit_event(
    db: Session,
    project_id: str,
    event_type: str,
    actor_type: str = "system",
    actor_id: str = "system",
    payload: dict | None = None,
) -> AuditEvent:
    """Record an audit event and return the created row."""
    event = AuditEvent(
        project_id=project_id,
        actor_type=actor_type,
        actor_id=actor_id,
        event_type=event_type,
        payload_json=payload,
    )
    db.add(event)
    db.flush()
    return event


def list_audit_events(
    db: Session,
    project_id: str,
    current_user: CurrentUser,
) -> list[dict[str, object]]:
    require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.read",
    )
    events = list_events_by_project(db, project_id)
    return [
        {
            "id": e.id,
            "project_id": e.project_id,
            "event_type": e.event_type,
            "actor_type": e.actor_type,
            "actor_id": e.actor_id,
            "payload": e.payload_json,
            "created_at": e.created_at.isoformat() if e.created_at else "",
        }
        for e in events
    ]
