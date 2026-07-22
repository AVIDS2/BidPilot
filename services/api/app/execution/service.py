from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import uuid4

from contracts.usage_ledger import release_model_reservation
from app.access.service import require_execution_run_capability, require_project_capability
from app.audit.service import record_audit_event
from app.auth.schemas import CurrentUser
from app.models import ExecutionRun, ProviderConfig, RuntimeRun, UsageEvent
from app.outbox.service import enqueue_workflow_task, request_task_outbox_dispatch
from app.runtime.service import create_workflow_bridge_run
from app.usage.schemas import ProviderSource
from app.usage.service import WORKFLOW_DRAFT_STARTED, check_workflow_quota, record_usage_event
from app.usage.service import attach_model_usage_reservation, reserve_workflow_model_tokens

from .repository import list_runs_by_project
from .schemas import ExecutionRunRead


_RETRYABLE_WORKFLOW_TYPES = {"draft_section", "redraft_section"}
_RETRYABLE_TERMINAL_STATUSES = {"failed", "cancelled"}
_TERMINAL_ATTEMPT_STATUSES = {"succeeded", "failed", "cancelled", "expired"}


def _to_read(run: ExecutionRun, *, runtime_run_id: str | None = None) -> ExecutionRunRead:
    input_json = run.input_json or {}
    input_runtime_run_id = input_json.get("runtime_run_id")
    return ExecutionRunRead(
        id=run.id,
        project_id=run.project_id,
        run_type=run.run_type,
        status=run.status,
        parent_execution_run_id=run.parent_execution_run_id,
        attempt_number=run.attempt_number,
        runtime_run_id=runtime_run_id
        if isinstance(runtime_run_id, str)
        else input_runtime_run_id
        if isinstance(input_runtime_run_id, str)
        else None,
        input_json=run.input_json,
        output_json=run.output_json,
    )


def get_run_query(
    db: Session,
    run_id: str,
    current_user: CurrentUser,
) -> ExecutionRunRead:
    run = require_execution_run_capability(
        db,
        current_user=current_user,
        run_id=run_id,
        capability="project.read",
    )
    return _to_read(run)


def list_runs_query(
    db: Session,
    project_id: str,
    current_user: CurrentUser,
) -> list[ExecutionRunRead]:
    require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.read",
    )
    runs = list_runs_by_project(db, project_id)
    return [_to_read(run) for run in runs]


def retry_failed_run_command(
    db: Session,
    run_id: str,
    current_user: CurrentUser,
) -> ExecutionRunRead:
    """Create a new, linked workflow attempt without mutating the source run."""
    authorized_source_run = require_execution_run_capability(
        db,
        current_user=current_user,
        run_id=run_id,
        capability="workflow.run",
    )
    source_run = db.scalar(
        select(ExecutionRun).where(ExecutionRun.id == authorized_source_run.id).with_for_update()
    )
    if source_run is None:
        raise HTTPException(status_code=404, detail="Execution run not found")
    if source_run.run_type not in _RETRYABLE_WORKFLOW_TYPES:
        raise HTTPException(status_code=400, detail="Only draft workflows can be retried")
    if source_run.status not in _RETRYABLE_TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Only failed or cancelled runs can be retried")

    section_key, review_feedback = _retryable_input(source_run)
    source_bridge = _workflow_bridge_for_execution_run(
        db,
        execution_run_id=source_run.id,
        org_id=current_user.org_id,
        project_id=source_run.project_id,
    )
    if source_bridge is None:
        raise HTTPException(
            status_code=409,
            detail="Legacy workflow cannot be retried safely; start a new draft instead",
        )
    if source_bridge.status not in _RETRYABLE_TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Workflow runtime is not in a retryable terminal state",
        )
    if source_bridge.status != source_run.status:
        raise HTTPException(
            status_code=409,
            detail="Workflow runtime state does not match execution state",
        )

    existing_child = db.scalar(
        select(ExecutionRun)
        .where(ExecutionRun.parent_execution_run_id == source_run.id)
        .order_by(ExecutionRun.attempt_number.desc())
        .limit(1)
    )
    if existing_child is not None:
        if existing_child.status not in _TERMINAL_ATTEMPT_STATUSES:
            child_bridge = _workflow_bridge_for_execution_run(
                db,
                execution_run_id=existing_child.id,
                org_id=current_user.org_id,
                project_id=source_run.project_id,
            )
            if child_bridge is None:
                raise HTTPException(status_code=409, detail="Existing retry attempt is missing its runtime bridge")
            return _to_read(existing_child, runtime_run_id=child_bridge.id)
        raise HTTPException(status_code=409, detail="A newer attempt already exists; retry that attempt instead")

    provider_config_id = _retry_provider_config_id(
        db,
        source_bridge,
        source_execution_run_id=source_run.id,
        user_id=current_user.id,
    )
    reasoning_effort = source_bridge.reasoning_effort
    provider_source = ProviderSource.BYOK if provider_config_id else ProviderSource.OFFICIAL
    check_workflow_quota(db, current_user.id, current_user.org_id, provider_source)
    provider_type = "openai"
    if provider_config_id:
        provider_config = db.get(ProviderConfig, provider_config_id)
        if provider_config is None:
            raise HTTPException(status_code=409, detail="Saved provider configuration is no longer available")
        provider_type = provider_config.provider_type

    retry_run = ExecutionRun(
        project_id=source_run.project_id,
        parent_execution_run_id=source_run.id,
        attempt_number=max(source_run.attempt_number, 1) + 1,
        run_type=source_run.run_type,
        input_json={
            "section_key": section_key,
            **({"review_feedback": review_feedback} if review_feedback else {}),
            "retry_of_execution_run_id": source_run.id,
        },
    )
    db.add(retry_run)
    db.flush()
    reservation_key = f"workflow:{uuid4()}"
    reservation = reserve_workflow_model_tokens(
        db,
        user_id=current_user.id,
        org_id=current_user.org_id,
        provider_source=provider_source,
        provider_type=provider_type,
        reservation_key=reservation_key,
        project_id=retry_run.project_id,
        execution_run_id=retry_run.id,
    )
    try:
        retry_bridge = create_workflow_bridge_run(
            db,
            current_user,
            execution_run_id=retry_run.id,
            project_id=retry_run.project_id,
            parent_run_id=source_bridge.id,
            provider_config_id=provider_config_id,
            reasoning_effort=reasoning_effort,
        )
    except Exception:
        if reservation is not None:
            release_model_reservation(
                db,
                org_id=current_user.org_id,
                reservation_key=reservation_key,
            )
            db.commit()
        else:
            db.rollback()
        raise
    attach_model_usage_reservation(
        db,
        reservation,
        execution_run_id=retry_run.id,
        runtime_run_id=retry_bridge.id,
    )
    retry_run.input_json = {
        **(retry_run.input_json or {}),
        "runtime_run_id": retry_bridge.id,
        "model_usage_reservation_key": reservation_key,
    }
    record_usage_event(
        db,
        user_id=current_user.id,
        org_id=current_user.org_id,
        project_id=retry_run.project_id,
        event_type=WORKFLOW_DRAFT_STARTED,
        provider_source=provider_source,
        execution_run_id=retry_run.id,
        metadata_json={
            "retry_of_execution_run_id": source_run.id,
            "attempt_number": retry_run.attempt_number,
        },
    )

    task_kwargs: dict[str, str] = {"runtime_run_id": retry_bridge.id}
    if review_feedback:
        task_kwargs["review_feedback"] = review_feedback
    if provider_config_id:
        task_kwargs["provider_config_id"] = provider_config_id
    if reasoning_effort:
        task_kwargs["reasoning_effort"] = reasoning_effort
    outbox_event = enqueue_workflow_task(
        db,
        org_id=current_user.org_id,
        project_id=retry_run.project_id,
        execution_run_id=retry_run.id,
        runtime_run_id=retry_bridge.id,
        task_name="worker.draft_section",
        args=[retry_run.id, retry_run.project_id, section_key],
        kwargs=task_kwargs,
        deduplication_key=f"workflow-run:{retry_run.id}",
    )
    record_audit_event(
        db,
        project_id=retry_run.project_id,
        event_type="run.retried",
        actor_type="user",
        actor_id=current_user.id,
        payload={
            "source_run_id": source_run.id,
            "retry_run_id": retry_run.id,
            "run_type": retry_run.run_type,
            "attempt_number": retry_run.attempt_number,
        },
    )
    db.commit()
    db.refresh(retry_run)
    request_task_outbox_dispatch(outbox_event.id)

    return _to_read(retry_run)


def _retryable_input(run: ExecutionRun) -> tuple[str, str | None]:
    input_json = run.input_json or {}
    section_key = input_json.get("section_key")
    if not isinstance(section_key, str) or not section_key.strip():
        raise HTTPException(status_code=400, detail="Draft workflow is missing its section key")
    review_feedback = input_json.get("review_feedback")
    return section_key.strip(), review_feedback if isinstance(review_feedback, str) and review_feedback.strip() else None


def _workflow_bridge_for_execution_run(
    db: Session,
    *,
    execution_run_id: str,
    org_id: str,
    project_id: str,
) -> RuntimeRun | None:
    return db.scalar(
        select(RuntimeRun)
        .where(
            RuntimeRun.execution_run_id == execution_run_id,
            RuntimeRun.kind == "workflow_bridge",
            RuntimeRun.org_id == org_id,
            RuntimeRun.project_id == project_id,
        )
        .order_by(RuntimeRun.created_at.desc())
    )


def _retry_provider_config_id(
    db: Session,
    source_bridge: RuntimeRun,
    *,
    source_execution_run_id: str,
    user_id: str,
) -> str | None:
    if source_bridge.provider_config_id is not None:
        config = db.get(ProviderConfig, source_bridge.provider_config_id)
        if config is not None and config.user_id == user_id:
            return config.id
        raise HTTPException(
            status_code=409,
            detail="Original provider configuration is not available to the current user",
        )

    persisted_source = (source_bridge.input_json or {}).get("provider_source")
    if persisted_source == ProviderSource.OFFICIAL.value:
        return None
    if persisted_source == ProviderSource.BYOK.value or _usage_recorded_byok_source(db, source_execution_run_id):
        raise HTTPException(
            status_code=409,
            detail="Original provider configuration is not available to the current user",
        )
    raise HTTPException(
        status_code=409,
        detail="Original provider source is unavailable; start a new draft instead",
    )


def _usage_recorded_byok_source(db: Session, execution_run_id: str) -> bool:
    provider_source = db.scalar(
        select(UsageEvent.provider_source)
        .where(
            UsageEvent.execution_run_id == execution_run_id,
            UsageEvent.event_type == WORKFLOW_DRAFT_STARTED,
        )
        .order_by(UsageEvent.created_at.desc())
        .limit(1)
    )
    return provider_source == ProviderSource.BYOK.value
