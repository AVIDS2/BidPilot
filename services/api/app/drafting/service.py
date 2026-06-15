from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.audit.service import record_audit_event
from app.celery_client import celery
from app.models import ExecutionRun

from .repository import create_run
from .schemas import DraftSectionRequest, DraftSectionResponse, RedraftSectionRequest, ResumeRunRequest
from app.usage.schemas import ProviderSource
from app.usage.service import (
    WORKFLOW_DRAFT_STARTED,
    UsageLimitExceeded,
    check_workflow_quota,
    record_usage_event,
)


def _provider_source(provider_config_id: str | None) -> ProviderSource:
    return ProviderSource.BYOK if provider_config_id else ProviderSource.OFFICIAL


def draft_section_command(
    db: Session,
    payload: DraftSectionRequest,
    current_user: CurrentUser | None = None,
) -> DraftSectionResponse:
    provider_source = _provider_source(payload.provider_config_id)
    if current_user is not None:
        check_workflow_quota(db, current_user.id, current_user.org_id, provider_source)
    run = ExecutionRun(
        project_id=payload.project_id,
        run_type="draft_section",
        input_json={"section_key": payload.section_key},
    )
    run = create_run(db, run)
    if current_user is not None:
        record_usage_event(
            db,
            user_id=current_user.id,
            org_id=current_user.org_id,
            project_id=payload.project_id,
            event_type=WORKFLOW_DRAFT_STARTED,
            provider_source=provider_source,
            execution_run_id=run.id,
        )
    # Dispatch async drafting task
    kwargs: dict = {}
    if payload.provider_config_id:
        kwargs["provider_config_id"] = payload.provider_config_id
    celery.send_task(
        "worker.draft_section",
        args=[run.id, payload.project_id, payload.section_key],
        kwargs=kwargs or None,
    )
    # Record audit event
    record_audit_event(db, project_id=payload.project_id, event_type="draft.requested", payload={"run_id": run.id, "section_key": payload.section_key})
    db.commit()
    return DraftSectionResponse(run_id=run.id, status=run.status)


def redraft_section_command(
    db: Session,
    payload: RedraftSectionRequest,
    current_user: CurrentUser | None = None,
) -> DraftSectionResponse:
    provider_source = _provider_source(payload.provider_config_id)
    if current_user is not None:
        check_workflow_quota(db, current_user.id, current_user.org_id, provider_source)
    run = ExecutionRun(
        project_id=payload.project_id,
        run_type="redraft_section",
        input_json={"section_key": payload.section_key, "review_feedback": payload.review_feedback},
    )
    run = create_run(db, run)
    if current_user is not None:
        record_usage_event(
            db,
            user_id=current_user.id,
            org_id=current_user.org_id,
            project_id=payload.project_id,
            event_type=WORKFLOW_DRAFT_STARTED,
            provider_source=provider_source,
            execution_run_id=run.id,
        )
    # Dispatch async drafting task with feedback
    task_kwargs: dict = {}
    if payload.review_feedback:
        task_kwargs["review_feedback"] = payload.review_feedback
    if payload.provider_config_id:
        task_kwargs["provider_config_id"] = payload.provider_config_id
    celery.send_task(
        "worker.draft_section",
        args=[run.id, payload.project_id, payload.section_key],
        kwargs=task_kwargs or None,
    )
    # Record audit event
    record_audit_event(db, project_id=payload.project_id, event_type="draft.redraft", payload={"run_id": run.id, "section_key": payload.section_key, "has_feedback": payload.review_feedback is not None})
    db.commit()
    return DraftSectionResponse(run_id=run.id, status=run.status)


def resume_run_command(db: Session, run_id: str, payload: ResumeRunRequest) -> DraftSectionResponse:
    """Resume an interrupted LangGraph drafting run.

    Validates that the run exists and is in a resumable state, then dispatches
    a Celery task that calls ``resume_graph`` on the worker side.

    Args:
        db: Database session.
        run_id: UUID of the ExecutionRun to resume.
        payload: Human decision and optional feedback.

    Returns:
        DraftSectionResponse with the run_id and updated status.

    Raises:
        ValueError: If the run does not exist.
        RuntimeError: If the run is not in a resumable state.
    """
    run = db.get(ExecutionRun, run_id)
    if run is None:
        raise ValueError(f"ExecutionRun {run_id} not found")

    if run.status not in ("pending", "running", "awaiting_human"):
        raise RuntimeError(
            f"ExecutionRun {run_id} is in state '{run.status}' and cannot be resumed"
        )

    # Map the API decision to the internal HITL decision value.
    # API uses "approved"/"rejected"; graph uses "approved"/"rejected_with_feedback".
    decision = payload.decision
    if decision == "rejected":
        decision = "rejected_with_feedback"

    # Update run status to indicate it's being resumed
    run.status = "running"
    db.flush()

    # Dispatch async task to resume the graph on the worker
    celery.send_task(
        "worker.resume_draft",
        args=[run_id, decision, payload.feedback],
    )

    # Record audit event
    record_audit_event(
        db,
        project_id=run.project_id,
        event_type="draft.resumed",
        payload={
            "run_id": run_id,
            "decision": payload.decision,
            "has_feedback": payload.feedback is not None,
        },
    )
    db.commit()

    return DraftSectionResponse(run_id=run_id, status=run.status)
