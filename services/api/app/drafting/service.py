from sqlalchemy.orm import Session

from app.audit.service import record_audit_event
from app.celery_client import celery
from app.models import ExecutionRun

from .repository import create_run
from .schemas import DraftSectionRequest, DraftSectionResponse, RedraftSectionRequest


def draft_section_command(db: Session, payload: DraftSectionRequest) -> DraftSectionResponse:
    run = ExecutionRun(
        project_id=payload.project_id,
        run_type="draft_section",
        input_json={"section_key": payload.section_key},
    )
    run = create_run(db, run)
    # Dispatch async drafting task
    celery.send_task(
        "worker.draft_section",
        args=[run.id, payload.project_id, payload.section_key],
    )
    # Record audit event
    record_audit_event(db, project_id=payload.project_id, event_type="draft.requested", payload={"run_id": run.id, "section_key": payload.section_key})
    db.commit()
    return DraftSectionResponse(run_id=run.id, status=run.status)


def redraft_section_command(db: Session, payload: RedraftSectionRequest) -> DraftSectionResponse:
    run = ExecutionRun(
        project_id=payload.project_id,
        run_type="redraft_section",
        input_json={"section_key": payload.section_key, "review_feedback": payload.review_feedback},
    )
    run = create_run(db, run)
    # Dispatch async drafting task with feedback
    celery.send_task(
        "worker.draft_section",
        args=[run.id, payload.project_id, payload.section_key],
        kwargs={"review_feedback": payload.review_feedback} if payload.review_feedback else {},
    )
    # Record audit event
    record_audit_event(db, project_id=payload.project_id, event_type="draft.redraft", payload={"run_id": run.id, "section_key": payload.section_key, "has_feedback": payload.review_feedback is not None})
    db.commit()
    return DraftSectionResponse(run_id=run.id, status=run.status)
