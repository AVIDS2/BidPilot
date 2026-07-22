from fastapi import HTTPException
from sqlalchemy.orm import Session
from uuid import uuid4

from contracts.models import ModelUsageReservation
from contracts.usage_ledger import release_model_reservation

from app.access.service import require_execution_run_capability, require_project_capability
from app.auth.schemas import CurrentUser
from app.audit.service import record_audit_event
from app.models import ExecutionRun, ProviderConfig
from app.outbox.service import enqueue_workflow_task, request_task_outbox_dispatch
from app.runtime.service import create_workflow_bridge_run

from .schemas import DraftSectionRequest, DraftSectionResponse, RedraftSectionRequest, ResumeRunRequest
from app.usage.schemas import ProviderSource
from app.usage.service import (
    WORKFLOW_DRAFT_STARTED,
    attach_model_usage_reservation,
    check_workflow_quota,
    record_usage_event,
    reserve_workflow_model_tokens,
)


def _provider_source(provider_config_id: str | None) -> ProviderSource:
    return ProviderSource.BYOK if provider_config_id else ProviderSource.OFFICIAL


def _provider_config_id_for_user(
    db: Session,
    current_user: CurrentUser,
    provider_config_id: str | None,
) -> str | None:
    if provider_config_id is None:
        return None
    config = db.get(ProviderConfig, provider_config_id)
    if config is None or config.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Provider config not found")
    return config.id


def _provider_type_for_config(db: Session, provider_config_id: str | None) -> str:
    if provider_config_id is None:
        return "openai"
    config = db.get(ProviderConfig, provider_config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Provider config not found")
    return config.provider_type


def _reserve_workflow_capacity(
    db: Session,
    *,
    current_user: CurrentUser,
    project_id: str,
    provider_source: ProviderSource,
    provider_type: str,
) -> tuple[str, ModelUsageReservation | None]:
    reservation_key = f"workflow:{uuid4()}"
    reservation = reserve_workflow_model_tokens(
        db,
        user_id=current_user.id,
        org_id=current_user.org_id,
        provider_source=provider_source,
        provider_type=provider_type,
        reservation_key=reservation_key,
        project_id=project_id,
    )
    return reservation_key, reservation


def _release_workflow_capacity(
    db: Session,
    *,
    current_user: CurrentUser,
    reservation_key: str,
    reservation: ModelUsageReservation | None,
) -> None:
    if reservation is None:
        db.rollback()
        return
    release_model_reservation(
        db,
        org_id=current_user.org_id,
        reservation_key=reservation_key,
    )
    db.commit()


def draft_section_command(
    db: Session,
    payload: DraftSectionRequest,
    current_user: CurrentUser,
) -> DraftSectionResponse:
    provider_config_id = _provider_config_id_for_user(db, current_user, payload.provider_config_id)
    provider_source = _provider_source(provider_config_id)
    provider_type = _provider_type_for_config(db, provider_config_id)
    require_project_capability(
        db,
        current_user=current_user,
        project_id=payload.project_id,
        capability="workflow.run",
    )
    check_workflow_quota(db, current_user.id, current_user.org_id, provider_source)
    reservation_key, reservation = _reserve_workflow_capacity(
        db,
        current_user=current_user,
        project_id=payload.project_id,
        provider_source=provider_source,
        provider_type=provider_type,
    )
    run = ExecutionRun(
        project_id=payload.project_id,
        run_type="draft_section",
        input_json={"section_key": payload.section_key},
    )
    db.add(run)
    db.flush()
    try:
        runtime_run = create_workflow_bridge_run(
            db,
            current_user,
            execution_run_id=run.id,
            project_id=payload.project_id,
            parent_run_id=payload.parent_runtime_run_id,
            provider_config_id=provider_config_id,
            reasoning_effort=payload.reasoning_effort,
        )
    except Exception:
        _release_workflow_capacity(
            db,
            current_user=current_user,
            reservation_key=reservation_key,
            reservation=reservation,
        )
        raise
    attach_model_usage_reservation(
        db,
        reservation,
        execution_run_id=run.id,
        runtime_run_id=runtime_run.id,
    )
    run.input_json = {
        **(run.input_json or {}),
        "runtime_run_id": runtime_run.id,
        "model_usage_reservation_key": reservation_key,
    }
    record_usage_event(
        db,
        user_id=current_user.id,
        org_id=current_user.org_id,
        project_id=payload.project_id,
        event_type=WORKFLOW_DRAFT_STARTED,
        provider_source=provider_source,
        execution_run_id=run.id,
    )
    # Persist a durable task intent in the same transaction as the workflow state.
    kwargs: dict = {}
    if provider_config_id:
        kwargs["provider_config_id"] = provider_config_id
    if payload.reasoning_effort:
        kwargs["reasoning_effort"] = payload.reasoning_effort
    kwargs["runtime_run_id"] = runtime_run.id
    outbox_event = enqueue_workflow_task(
        db,
        org_id=current_user.org_id,
        project_id=payload.project_id,
        execution_run_id=run.id,
        runtime_run_id=runtime_run.id,
        task_name="worker.draft_section",
        args=[run.id, payload.project_id, payload.section_key],
        kwargs=kwargs,
        deduplication_key=f"workflow-run:{run.id}",
    )
    # Record audit event
    record_audit_event(
        db,
        project_id=payload.project_id,
        event_type="draft.requested",
        actor_type="user",
        actor_id=current_user.id,
        payload={"run_id": run.id, "section_key": payload.section_key},
    )
    db.commit()
    request_task_outbox_dispatch(outbox_event.id)
    return DraftSectionResponse(run_id=run.id, status=run.status, runtime_run_id=runtime_run.id)


def redraft_section_command(
    db: Session,
    payload: RedraftSectionRequest,
    current_user: CurrentUser,
) -> DraftSectionResponse:
    provider_config_id = _provider_config_id_for_user(db, current_user, payload.provider_config_id)
    provider_source = _provider_source(provider_config_id)
    provider_type = _provider_type_for_config(db, provider_config_id)
    require_project_capability(
        db,
        current_user=current_user,
        project_id=payload.project_id,
        capability="workflow.run",
    )
    check_workflow_quota(db, current_user.id, current_user.org_id, provider_source)
    reservation_key, reservation = _reserve_workflow_capacity(
        db,
        current_user=current_user,
        project_id=payload.project_id,
        provider_source=provider_source,
        provider_type=provider_type,
    )
    run = ExecutionRun(
        project_id=payload.project_id,
        run_type="redraft_section",
        input_json={"section_key": payload.section_key, "review_feedback": payload.review_feedback},
    )
    db.add(run)
    db.flush()
    try:
        runtime_run = create_workflow_bridge_run(
            db,
            current_user,
            execution_run_id=run.id,
            project_id=payload.project_id,
            parent_run_id=payload.parent_runtime_run_id,
            provider_config_id=provider_config_id,
            reasoning_effort=payload.reasoning_effort,
        )
    except Exception:
        _release_workflow_capacity(
            db,
            current_user=current_user,
            reservation_key=reservation_key,
            reservation=reservation,
        )
        raise
    attach_model_usage_reservation(
        db,
        reservation,
        execution_run_id=run.id,
        runtime_run_id=runtime_run.id,
    )
    run.input_json = {
        **(run.input_json or {}),
        "runtime_run_id": runtime_run.id,
        "model_usage_reservation_key": reservation_key,
    }
    record_usage_event(
        db,
        user_id=current_user.id,
        org_id=current_user.org_id,
        project_id=payload.project_id,
        event_type=WORKFLOW_DRAFT_STARTED,
        provider_source=provider_source,
        execution_run_id=run.id,
    )
    # Persist the redraft delivery with the rest of its durable workflow state.
    task_kwargs: dict = {}
    if payload.review_feedback:
        task_kwargs["review_feedback"] = payload.review_feedback
    if provider_config_id:
        task_kwargs["provider_config_id"] = provider_config_id
    if payload.reasoning_effort:
        task_kwargs["reasoning_effort"] = payload.reasoning_effort
    task_kwargs["runtime_run_id"] = runtime_run.id
    outbox_event = enqueue_workflow_task(
        db,
        org_id=current_user.org_id,
        project_id=payload.project_id,
        execution_run_id=run.id,
        runtime_run_id=runtime_run.id,
        task_name="worker.draft_section",
        args=[run.id, payload.project_id, payload.section_key],
        kwargs=task_kwargs,
        deduplication_key=f"workflow-run:{run.id}",
    )
    # Record audit event
    record_audit_event(
        db,
        project_id=payload.project_id,
        event_type="draft.redraft",
        actor_type="user",
        actor_id=current_user.id,
        payload={
            "run_id": run.id,
            "section_key": payload.section_key,
            "has_feedback": payload.review_feedback is not None,
        },
    )
    db.commit()
    request_task_outbox_dispatch(outbox_event.id)
    return DraftSectionResponse(run_id=run.id, status=run.status, runtime_run_id=runtime_run.id)


def resume_run_command(
    db: Session,
    run_id: str,
    payload: ResumeRunRequest,
    current_user: CurrentUser,
) -> DraftSectionResponse:
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
    run = require_execution_run_capability(
        db,
        current_user=current_user,
        run_id=run_id,
        capability="workflow.run",
    )

    if run.status != "awaiting_human":
        raise RuntimeError(
            f"ExecutionRun {run_id} is in state '{run.status}' and is not awaiting human approval"
        )

    # Map the API decision to the internal HITL decision value.
    # API uses "approved"/"rejected"; graph uses "approved"/"rejected_with_feedback".
    decision = payload.decision
    if decision == "rejected":
        decision = "rejected_with_feedback"

    # The sequence distinguishes a later approval cycle for the same graph run.
    input_json = dict(run.input_json or {})
    existing_sequence = input_json.get("resume_sequence")
    resume_sequence = existing_sequence + 1 if type(existing_sequence) is int and existing_sequence >= 0 else 1
    input_json["resume_sequence"] = resume_sequence
    run.input_json = input_json

    # Update run status to indicate it is being resumed, then persist the task intent.
    run.status = "running"
    db.flush()

    runtime_run_id = input_json.get("runtime_run_id")
    outbox_event = enqueue_workflow_task(
        db,
        org_id=current_user.org_id,
        project_id=run.project_id,
        execution_run_id=run.id,
        runtime_run_id=runtime_run_id if isinstance(runtime_run_id, str) else None,
        task_name="worker.resume_draft",
        args=[run_id, decision, payload.feedback],
        kwargs={},
        deduplication_key=f"workflow-resume:{run_id}:{resume_sequence}",
    )

    # Record audit event
    record_audit_event(
        db,
        project_id=run.project_id,
        event_type="draft.resumed",
        actor_type="user",
        actor_id=current_user.id,
        payload={
            "run_id": run_id,
            "decision": payload.decision,
            "has_feedback": payload.feedback is not None,
        },
    )
    db.commit()
    request_task_outbox_dispatch(outbox_event.id)

    return DraftSectionResponse(run_id=run_id, status=run.status)
