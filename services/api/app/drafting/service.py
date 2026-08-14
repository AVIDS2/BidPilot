from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import uuid4

from contracts.models import ModelUsageReservation
from contracts.usage_ledger import release_model_reservation

from app.access.service import require_execution_run_capability, require_project_capability
from app.auth.schemas import CurrentUser
from app.audit.service import record_audit_event
from app.models import Deliverable, DeliverableSection, ExecutionRun, ProviderConfig, SectionVersion
from app.outbox.service import enqueue_workflow_task, request_task_outbox_dispatch
from app.review.decision_service import apply_review_decision
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


def _request_fingerprint(
    *,
    section_key: str,
    section_id: str | None,
    provider_config_id: str | None,
    reasoning_effort: str | None,
    max_iterations: int | None,
    review_feedback: str | None = None,
) -> dict[str, object | None]:
    """Store the user-visible intent needed to reject key reuse safely."""
    return {
        "section_key": section_key,
        "section_id": section_id,
        "provider_config_id": provider_config_id,
        "reasoning_effort": reasoning_effort,
        "max_iterations": max_iterations,
        "review_feedback": review_feedback,
    }


def _resolve_draft_section_id(
    db: Session,
    *,
    project_id: str,
    section_key: str,
    section_id: str | None,
) -> str | None:
    """Resolve one exact draft target without guessing across deliverables.

    Old API/agent callers may still provide only a section key. That remains
    valid while the key names a single section in the project. Once two
    deliverables contain the same key, callers must send the concrete section
    id returned by the outline/sections endpoints.
    """
    if section_id:
        section = db.get(DeliverableSection, section_id)
        deliverable = db.get(Deliverable, section.deliverable_id) if section else None
        if section is None or deliverable is None or deliverable.project_id != project_id:
            raise HTTPException(status_code=404, detail="deliverable_section_not_found")
        if section.section_key != section_key:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "section_target_mismatch",
                    "message": "section_id 与 section_key 不匹配。",
                },
            )
        return section.id

    matches = list(
        db.scalars(
            select(DeliverableSection)
            .join(Deliverable, Deliverable.id == DeliverableSection.deliverable_id)
            .where(
                Deliverable.project_id == project_id,
                DeliverableSection.section_key == section_key,
            )
            .order_by(DeliverableSection.id.asc())
            .limit(2)
        ).all()
    )
    if len(matches) > 1:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "section_key_ambiguous",
                "message": "该项目存在多个同名章节，请指定 section_id 后再启动工作流。",
                "section_key": section_key,
                "section_ids": [section.id for section in matches],
            },
        )
    return matches[0].id if matches else None


def _replay_existing_draft_request(
    db: Session,
    *,
    current_user: CurrentUser,
    project_id: str,
    run_type: str,
    client_request_id: str | None,
    fingerprint: dict[str, str | None],
) -> DraftSectionResponse | None:
    """Return an existing accepted draft request instead of starting it again.

    A request ID is user-scoped and may be replayed after a browser retry.  It
    must never be silently reused for a different project or section.
    """
    if not client_request_id:
        return None

    existing = db.scalar(
        select(ExecutionRun)
        .where(
            ExecutionRun.requested_by_user_id == current_user.id,
            ExecutionRun.client_request_id == client_request_id,
        )
        .with_for_update()
    )
    if existing is None:
        return None

    stored_input = existing.input_json or {}
    stored_fingerprint = stored_input.get("request_fingerprint")
    if (
        existing.project_id != project_id
        or existing.run_type != run_type
        or (
            isinstance(stored_fingerprint, dict)
            and stored_fingerprint != fingerprint
        )
        or (
            not isinstance(stored_fingerprint, dict)
            and stored_input.get("section_key") != fingerprint["section_key"]
        )
    ):
        raise HTTPException(
            status_code=409,
            detail="client_request_id was already used for a different workflow request",
        )

    runtime_run_id = stored_input.get("runtime_run_id")
    return DraftSectionResponse(
        run_id=existing.id,
        status=existing.status,
        runtime_run_id=runtime_run_id if isinstance(runtime_run_id, str) else None,
    )


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
    require_project_capability(
        db,
        current_user=current_user,
        project_id=payload.project_id,
        capability="workflow.run",
    )
    section_id = _resolve_draft_section_id(
        db,
        project_id=payload.project_id,
        section_key=payload.section_key,
        section_id=payload.section_id,
    )
    request_fingerprint = _request_fingerprint(
        section_key=payload.section_key,
        section_id=section_id,
        provider_config_id=provider_config_id,
        reasoning_effort=payload.reasoning_effort,
        max_iterations=payload.max_iterations,
    )
    replay = _replay_existing_draft_request(
        db,
        current_user=current_user,
        project_id=payload.project_id,
        run_type="draft_section",
        client_request_id=payload.client_request_id,
        fingerprint=request_fingerprint,
    )
    if replay is not None:
        return replay
    provider_source = _provider_source(provider_config_id)
    provider_type = _provider_type_for_config(db, provider_config_id)
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
        requested_by_user_id=current_user.id,
        client_request_id=payload.client_request_id,
        input_json={
            "section_key": payload.section_key,
            "section_id": section_id,
            "max_iterations": payload.max_iterations,
            "request_fingerprint": request_fingerprint,
        },
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
    if payload.max_iterations is not None:
        kwargs["max_iterations"] = payload.max_iterations
    kwargs["runtime_run_id"] = runtime_run.id
    if section_id:
        kwargs["deliverable_section_id"] = section_id
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
        payload={"run_id": run.id, "section_key": payload.section_key, "section_id": section_id},
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
    require_project_capability(
        db,
        current_user=current_user,
        project_id=payload.project_id,
        capability="workflow.run",
    )
    section_id = _resolve_draft_section_id(
        db,
        project_id=payload.project_id,
        section_key=payload.section_key,
        section_id=payload.section_id,
    )
    request_fingerprint = _request_fingerprint(
        section_key=payload.section_key,
        section_id=section_id,
        provider_config_id=provider_config_id,
        reasoning_effort=payload.reasoning_effort,
        max_iterations=payload.max_iterations,
        review_feedback=payload.review_feedback,
    )
    replay = _replay_existing_draft_request(
        db,
        current_user=current_user,
        project_id=payload.project_id,
        run_type="redraft_section",
        client_request_id=payload.client_request_id,
        fingerprint=request_fingerprint,
    )
    if replay is not None:
        return replay
    provider_source = _provider_source(provider_config_id)
    provider_type = _provider_type_for_config(db, provider_config_id)
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
        requested_by_user_id=current_user.id,
        client_request_id=payload.client_request_id,
        input_json={
            "section_key": payload.section_key,
            "section_id": section_id,
            "review_feedback": payload.review_feedback,
            "max_iterations": payload.max_iterations,
            "request_fingerprint": request_fingerprint,
        },
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
    if payload.max_iterations is not None:
        task_kwargs["max_iterations"] = payload.max_iterations
    task_kwargs["runtime_run_id"] = runtime_run.id
    if section_id:
        task_kwargs["deliverable_section_id"] = section_id
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
            "section_id": section_id,
            "has_feedback": payload.review_feedback is not None,
        },
    )
    db.commit()
    request_task_outbox_dispatch(outbox_event.id)
    return DraftSectionResponse(run_id=run.id, status=run.status, runtime_run_id=runtime_run.id)


def queue_resume_draft_run(
    db: Session,
    *,
    run: ExecutionRun,
    current_user: CurrentUser,
    decision: str,
    feedback: str | None,
    review_thread_id: str | None = None,
    section_version_id: str | None = None,
):
    """Write one sequenced, version-bound resume intent without dispatching it.

    The broker payload remains intentionally small, but a LangGraph resume must
    be anchored to the immutable candidate and final ReviewThread decision that
    caused it. The worker re-reads this durable reference before resuming a
    checkpoint, rather than trusting an at-least-once queue payload.
    """
    if run.status != "awaiting_human":
        raise RuntimeError(
            f"ExecutionRun {run.id} is in state '{run.status}' and is not awaiting human approval"
        )

    graph_decision = "rejected_with_feedback" if decision == "rejected" else "approved"
    input_json = dict(run.input_json or {})
    existing_sequence = input_json.get("resume_sequence")
    resume_sequence = existing_sequence + 1 if type(existing_sequence) is int and existing_sequence >= 0 else 1
    input_json["resume_sequence"] = resume_sequence
    if review_thread_id and section_version_id:
        input_json["review_resume"] = {
            "sequence": resume_sequence,
            "review_thread_id": review_thread_id,
            "section_version_id": section_version_id,
        }
    else:
        # Keep legacy resume support explicit and avoid inheriting a stale
        # candidate reference when a non-review interruption is resumed.
        input_json.pop("review_resume", None)
    run.input_json = input_json
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
        args=[run.id, graph_decision, feedback],
        kwargs={},
        deduplication_key=f"workflow-resume:{run.id}:{resume_sequence}",
    )
    record_audit_event(
        db,
        project_id=run.project_id,
        event_type="draft.resumed",
        actor_type="user",
        actor_id=current_user.id,
        payload={
            "run_id": run.id,
            "decision": decision,
            "has_feedback": feedback is not None,
            "review_thread_id": review_thread_id,
            "section_version_id": section_version_id,
        },
    )
    return outbox_event


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

    candidate = db.scalar(
        select(SectionVersion)
        .where(SectionVersion.generation_run_id == run.id)
        .order_by(SectionVersion.generation_iteration.desc(), SectionVersion.version_number.desc())
        .limit(1)
    )
    review_thread_id: str | None = None
    if candidate is not None:
        section = db.get(DeliverableSection, candidate.deliverable_section_id)
        if section is not None:
            review_thread, _, _ = apply_review_decision(
                db,
                section=section,
                version=candidate,
                decision=payload.decision,
                current_user=current_user,
                comment=payload.feedback,
            )
            review_thread_id = review_thread.id

    outbox_event = queue_resume_draft_run(
        db,
        run=run,
        current_user=current_user,
        decision=payload.decision,
        feedback=payload.feedback,
        review_thread_id=review_thread_id,
        section_version_id=candidate.id if candidate is not None else None,
    )
    db.commit()
    request_task_outbox_dispatch(outbox_event.id)

    return DraftSectionResponse(run_id=run_id, status=run.status)
