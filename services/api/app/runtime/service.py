"""Idempotent capability execution and durable approval lifecycle."""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import logging
from typing import Any
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.assistant.audit import redact_arguments, redact_text
from app.access.service import require_project_capability
from app.audit.service import record_audit_event
from app.auth.schemas import CurrentUser
from app.models import ExecutionRun, Project, RuntimeAction, RuntimeApproval, RuntimeEvent, RuntimeRun
from contracts.runtime import (
    RuntimeActionStatus,
    RuntimeApprovalDecisionType,
    RuntimeApprovalStatus,
    RuntimeEventType,
    RuntimePolicyOutcome,
    RuntimeRunStatus,
)

from .failures import classify_capability_failure
from .events import RuntimeEventDraft, append_events, publish_event
from .policy import evaluate_policy
from .registry import (
    PublicCapabilityResult,
    format_approval_request,
    format_public_result,
    get_capability_definition,
    missing_required_capability_arguments,
)
from .repository import (
    RuntimeRunListRow,
    get_runtime_run_for_update,
    get_visible_runtime_run,
    list_visible_runtime_runs,
)


logger = logging.getLogger(__name__)


CapabilityExecutor = Callable[[Session, CurrentUser, dict[str, Any]], dict[str, Any]]


class RuntimeApprovalExpiredError(ValueError):
    """Raised when an approval has expired before a decision is applied."""


class RuntimeApprovalResolvedError(ValueError):
    """Raised when an approval is not pending anymore."""


@dataclass(frozen=True)
class RuntimeCapabilityExecution:
    action: RuntimeAction
    approval: RuntimeApproval | None = None
    result: PublicCapabilityResult | None = None


@dataclass(frozen=True)
class RuntimeRunCreation:
    """Result of an idempotent runtime-run creation attempt."""

    run: RuntimeRun
    created: bool


def get_previous_terminal_action_context(
    db: Session,
    user: CurrentUser,
    *,
    conversation_id: str,
    exclude_run_id: str,
) -> dict[str, Any] | None:
    """Return the latest trusted action failure for the next model turn.

    Conversation prose is not a reliable source for deciding whether a prior
    mutation actually ran. This small server-owned observation lets the model
    explain a failure or choose a different action without replaying raw audit
    data, arguments, or internal identifiers.
    """

    action = db.scalar(
        select(RuntimeAction)
        .join(RuntimeRun, RuntimeAction.run_id == RuntimeRun.id)
        .where(
            RuntimeRun.conversation_id == conversation_id,
            RuntimeRun.org_id == user.org_id,
            RuntimeRun.user_id == user.id,
            RuntimeRun.id != exclude_run_id,
            RuntimeAction.status.in_(
                (
                    RuntimeActionStatus.FAILED.value,
                    RuntimeActionStatus.DENIED.value,
                    RuntimeActionStatus.EXPIRED.value,
                )
            ),
        )
        .order_by(RuntimeAction.completed_at.desc(), RuntimeAction.created_at.desc())
        .limit(1)
    )
    if action is None:
        return None
    return {
        "capability_name": action.capability_name,
        "status": action.status,
        "error_code": action.error_code or "capability_execution_failed",
        "message": action.error_message or action.public_summary or "上一项操作未能完成。",
        "occurred_at": (action.completed_at or action.created_at).isoformat(),
    }


def _action_event_payload(action: RuntimeAction, **payload: Any) -> dict[str, Any]:
    """Return the stable, public correlation fields for one action event."""
    value: dict[str, Any] = {
        "capability": action.capability_name,
        "action_id": action.id,
    }
    if action.turn_id:
        value["turn_id"] = action.turn_id
    if action.tool_call_id:
        value["tool_call_id"] = action.tool_call_id
    # RuntimeAction stores redacted arguments for audit and operator diagnosis.
    # Do not replay them through every ordinary conversation event. Approval
    # events explicitly add the small, editable subset they need to render.
    value.update(payload)
    return value


def list_runtime_runs_query(
    db: Session,
    current_user: CurrentUser,
    *,
    limit: int = 50,
    conversation_id: str | None = None,
    kinds: Sequence[str] | None = None,
) -> list[RuntimeRunListRow]:
    """Return a bounded, permission-scoped list for the Run Center / history restore."""

    return list_visible_runtime_runs(
        db,
        current_user=current_user,
        limit=max(1, min(limit, 100)),
        conversation_id=conversation_id,
        kinds=kinds,
    )


def assistant_turn_idempotency_key(*, user_id: str, client_request_id: str | None) -> str | None:
    """Build an opaque, user-scoped key for one browser-originated assistant turn."""
    if not client_request_id:
        return None
    material = f"assistant-turn:{user_id}:{client_request_id}".encode("utf-8")
    return f"assistant:{sha256(material).hexdigest()}"


def find_idempotent_runtime_run(
    db: Session,
    user: CurrentUser,
    *,
    idempotency_key: str | None,
) -> RuntimeRun | None:
    """Find a caller's prior run for a client-generated request identifier.

    This is intentionally scoped to both the organization and the initiating
    user. A repeated browser request can resume its own durable trace, while a
    guessed key can never reveal another member's run.
    """
    if not idempotency_key:
        return None
    existing = db.scalar(
        select(RuntimeRun).where(
            RuntimeRun.org_id == user.org_id,
            RuntimeRun.idempotency_key == idempotency_key,
        )
    )
    if existing is not None and existing.user_id != user.id:
        raise HTTPException(status_code=409, detail="Idempotency key is already in use")
    return existing


def create_or_get_runtime_run(
    db: Session,
    user: CurrentUser,
    *,
    kind: str,
    engine: str,
    project_id: str | None = None,
    conversation_id: str | None = None,
    execution_run_id: str | None = None,
    parent_run_id: str | None = None,
    provider_config_id: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    approval_mode: str = "risky_only",
    idempotency_key: str | None = None,
    input_json: dict[str, Any] | None = None,
    initial_status: str = "running",
    commit: bool = True,
) -> RuntimeRunCreation:
    """Atomically create one runtime run or return the prior idempotent run.

    The read before insert handles normal browser retries cheaply. The unique
    constraint plus savepoint handles concurrent retries, where two requests
    observe no prior run at the same time.
    """
    if approval_mode not in {"request_approval", "risky_only", "full_access", "custom"}:
        raise ValueError(f"Invalid approval mode: {approval_mode}")
    if initial_status not in {"queued", "running"}:
        raise ValueError(f"Invalid initial runtime status: {initial_status}")
    if project_id is not None:
        require_project_capability(
            db,
            current_user=user,
            project_id=project_id,
            capability="project.read",
        )
    existing = find_idempotent_runtime_run(
        db,
        user,
        idempotency_key=idempotency_key,
    )
    if existing is not None:
        return RuntimeRunCreation(run=existing, created=False)

    run = RuntimeRun(
        kind=kind,
        status=initial_status,
        org_id=user.org_id,
        user_id=user.id,
        project_id=project_id,
        conversation_id=conversation_id,
        execution_run_id=execution_run_id,
        parent_run_id=parent_run_id,
        engine=engine,
        trace_id=str(uuid.uuid4()),
        idempotency_key=idempotency_key,
        provider_config_id=provider_config_id,
        model=model,
        reasoning_effort=reasoning_effort,
        policy_snapshot_json={"approval_mode": approval_mode, "allow_network": False},
        input_json=redact_arguments(input_json or {}),
        started_at=_now(),
    )
    try:
        # A savepoint keeps the outer request transaction usable when another
        # request wins the unique (org_id, idempotency_key) race.
        with db.begin_nested():
            db.add(run)
            db.flush()
    except IntegrityError:
        existing = find_idempotent_runtime_run(
            db,
            user,
            idempotency_key=idempotency_key,
        )
        if existing is None:
            raise
        return RuntimeRunCreation(run=existing, created=False)

    started_event = RuntimeEventDraft(
        type=RuntimeEventType.RUN_STARTED,
        public_summary="任务已开始。",
        payload={"kind": run.kind, "engine": run.engine},
    )
    if commit:
        # The run and its initial event become visible together. A replay can
        # therefore never attach to a run that has no durable trace yet.
        append_events(db, run.id, [started_event])
        db.commit()
        db.refresh(run)
    else:
        append_events(db, run.id, [started_event])
    return RuntimeRunCreation(run=run, created=True)


def create_runtime_run(
    db: Session,
    user: CurrentUser,
    *,
    kind: str,
    engine: str,
    project_id: str | None = None,
    conversation_id: str | None = None,
    execution_run_id: str | None = None,
    parent_run_id: str | None = None,
    provider_config_id: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    approval_mode: str = "risky_only",
    idempotency_key: str | None = None,
    input_json: dict[str, Any] | None = None,
    initial_status: str = "running",
    commit: bool = True,
) -> RuntimeRun:
    """Compatibility wrapper for callers that do not need creation state."""
    return create_or_get_runtime_run(
        db,
        user,
        kind=kind,
        engine=engine,
        project_id=project_id,
        conversation_id=conversation_id,
        execution_run_id=execution_run_id,
        parent_run_id=parent_run_id,
        provider_config_id=provider_config_id,
        model=model,
        reasoning_effort=reasoning_effort,
        approval_mode=approval_mode,
        idempotency_key=idempotency_key,
        input_json=input_json,
        initial_status=initial_status,
        commit=commit,
    ).run


def record_runtime_context_trace(
    db: Session,
    run: RuntimeRun,
    *,
    trace: dict[str, Any],
) -> RuntimeRun:
    """Persist content-free prompt assembly metadata for one runtime turn."""
    input_json = dict(run.input_json or {})
    input_json["context_assembly"] = redact_arguments(trace)
    run.input_json = input_json
    db.commit()
    db.refresh(run)
    return run


def create_workflow_bridge_run(
    db: Session,
    user: CurrentUser,
    *,
    execution_run_id: str,
    project_id: str,
    parent_run_id: str | None = None,
    provider_config_id: str | None = None,
    reasoning_effort: str | None = None,
    engine: str = "langgraph_workflow",
    commit: bool = True,
) -> RuntimeRun:
    """Create one durable runtime bridge for a long-running workflow job."""
    parent: RuntimeRun | None = None
    if parent_run_id:
        parent = get_visible_runtime_run(db, parent_run_id, user)
        if parent.project_id is not None and parent.project_id != project_id:
            raise ValueError("Parent runtime run belongs to a different project")

    existing = db.scalar(
        select(RuntimeRun).where(
            RuntimeRun.org_id == user.org_id,
            RuntimeRun.execution_run_id == execution_run_id,
        )
    )
    if existing is not None:
        get_visible_runtime_run(db, existing.id, user)
        return existing

    bridge = create_runtime_run(
        db,
        user,
        kind="workflow_bridge",
        engine=engine,
        project_id=project_id,
        conversation_id=parent.conversation_id if parent is not None else None,
        execution_run_id=execution_run_id,
        parent_run_id=parent.id if parent is not None else None,
        provider_config_id=provider_config_id,
        reasoning_effort=reasoning_effort,
        idempotency_key=f"workflow:{execution_run_id}",
        input_json={
            "execution_run_id": execution_run_id,
            "provider_source": "byok" if provider_config_id else "official",
        },
        commit=commit,
    )
    if parent is not None:
        linked_event = RuntimeEventDraft(
            type=RuntimeEventType.WORKFLOW_LINKED,
            public_summary="已创建工作流执行任务。",
            payload={
                "execution_run_id": execution_run_id,
                "workflow_runtime_run_id": bridge.id,
            },
        )
        if commit:
            publish_event(db, parent.id, linked_event)
        else:
            append_events(db, parent.id, [linked_event])
    return bridge


def list_linked_workflow_runs(
    db: Session,
    current_user: CurrentUser,
    *,
    parent_run_id: str,
    limit: int = 50,
) -> list[RuntimeRun]:
    """Return the durable workflow children owned by one assistant run.

    A single harness turn may start several governed workflows (for example a
    bounded draft campaign).  The child rows, not transient task objects, are
    the source of truth for that one-to-many relationship and each child has
    its own replayable RuntimeEvent timeline.
    """
    parent = get_visible_runtime_run(db, parent_run_id, current_user)
    children = list(
        db.scalars(
            select(RuntimeRun)
            .where(
                RuntimeRun.parent_run_id == parent.id,
                RuntimeRun.kind.in_(("workflow_bridge", "deep_research", "remote_import")),
                RuntimeRun.org_id == current_user.org_id,
                RuntimeRun.user_id == current_user.id,
            )
            .order_by(RuntimeRun.created_at.asc(), RuntimeRun.id.asc())
            .limit(max(1, min(limit, 100)))
        )
    )
    # ``created_at`` is only second/microsecond-resolution depending on the
    # database.  A parent RuntimeEvent already gives every launched child a
    # durable, monotonic sequence, so use it as the canonical visual/runtime
    # order when it is available.
    linked_events = list(
        db.scalars(
            select(RuntimeEvent)
            .where(
                RuntimeEvent.run_id == parent.id,
                RuntimeEvent.event_type == RuntimeEventType.WORKFLOW_LINKED.value,
            )
            .order_by(RuntimeEvent.sequence.asc())
        )
    )
    linked_sequence_by_child_id = {
        event.payload_json.get("workflow_runtime_run_id"): event.sequence
        for event in linked_events
        if isinstance(event.payload_json, dict)
        and isinstance(event.payload_json.get("workflow_runtime_run_id"), str)
    }
    return sorted(
        children,
        key=lambda child: (
            linked_sequence_by_child_id.get(child.id, 2**31 - 1),
            child.created_at,
            child.id,
        ),
    )


def list_runtime_child_runs(
    db: Session,
    current_user: CurrentUser,
    *,
    parent_run_id: str,
    limit: int = 20,
) -> list[RuntimeRunListRow]:
    """Return direct, visible child runs without exposing their private input."""

    parent = get_visible_runtime_run(db, parent_run_id, current_user)
    latest_event_summary = (
        select(RuntimeEvent.public_summary)
        .where(RuntimeEvent.run_id == RuntimeRun.id)
        .order_by(RuntimeEvent.sequence.desc())
        .limit(1)
        .scalar_subquery()
    )
    rows = db.execute(
        select(RuntimeRun, latest_event_summary.label("latest_event_summary"))
        .where(
            RuntimeRun.parent_run_id == parent.id,
            RuntimeRun.org_id == parent.org_id,
            RuntimeRun.kind == "subagent",
        )
        .order_by(RuntimeRun.created_at.asc(), RuntimeRun.id.asc())
        .limit(max(1, min(limit, 100)))
    ).all()
    return [
        RuntimeRunListRow(
            run=run,
            project_name=None,
            latest_event_summary=event_summary,
        )
        for run, event_summary in rows
    ]


def complete_runtime_run(
    db: Session,
    run_id: str,
    message: str,
    *,
    result_json: dict[str, Any] | None = None,
    parent_event_id: str | None = None,
    message_delta_emitted: bool = False,
    terminal_state: str | None = None,
) -> RuntimeRun:
    """Persist the user-facing result and terminal events as one transaction.

    Replaying a completed turn is intentionally a no-op.  This makes retries
    after an interrupted HTTP/SSE connection safe without duplicating the final
    assistant message in the event timeline.
    """
    return _finish_runtime_run(
        db,
        run_id,
        message,
        terminal_status="succeeded",
        terminal_event=RuntimeEventType.RUN_COMPLETED,
        terminal_summary="任务已完成。",
        allowed_statuses={"running"},
        result_json=result_json,
        parent_event_id=parent_event_id,
        message_delta_emitted=message_delta_emitted,
        terminal_state=terminal_state,
    )


def await_runtime_input(
    db: Session,
    run_id: str,
) -> RuntimeRun:
    """Persist a structured user-input pause without faking a successful run."""
    run = get_runtime_run_for_update(db, run_id)
    if run is None:
        raise ValueError("Runtime run not found")
    if run.status == RuntimeRunStatus.AWAITING_INPUT.value:
        return run
    if run.status in {"succeeded", "failed", "cancelled", "expired"}:
        return run
    if run.status != RuntimeRunStatus.RUNNING.value:
        raise ValueError(f"Cannot await input for runtime run in status: {run.status}")
    run.status = RuntimeRunStatus.AWAITING_INPUT.value
    db.commit()
    db.refresh(run)
    return run


def fail_runtime_run(
    db: Session,
    run_id: str,
    message: str,
    *,
    error_code: str = "runtime_failed",
    result_json: dict[str, Any] | None = None,
    parent_event_id: str | None = None,
    message_delta_emitted: bool = False,
) -> RuntimeRun:
    """Record a safe terminal failure without leaking provider or tool details."""
    return _finish_runtime_run(
        db,
        run_id,
        message,
        terminal_status="failed",
        terminal_event=RuntimeEventType.RUN_FAILED,
        terminal_summary="任务未能完成。",
        allowed_statuses={"queued", "running", "awaiting_approval", "awaiting_input", "cancel_requested"},
        result_json=result_json,
        error_code=error_code,
        parent_event_id=parent_event_id,
        message_delta_emitted=message_delta_emitted,
    )


def cancel_runtime_run(
    db: Session,
    run_id: str,
    message: str = "已取消这次操作。",
    *,
    parent_event_id: str | None = None,
) -> RuntimeRun:
    """Persist a user-requested cancellation and its terminal evidence."""
    return _finish_runtime_run(
        db,
        run_id,
        message,
        terminal_status="cancelled",
        terminal_event=RuntimeEventType.RUN_CANCELLED,
        terminal_summary="任务已取消。",
        allowed_statuses={"queued", "running", "awaiting_approval", "awaiting_input", "cancel_requested"},
        parent_event_id=parent_event_id,
    )


def request_runtime_cancellation(
    db: Session,
    user: CurrentUser,
    *,
    run_id: str,
) -> RuntimeRun:
    """Request a governed stop for either an assistant turn or workflow bridge.

    Workflow bridges keep their worker-safe cancellation protocol. Assistant
    turns are stopped at the next model/tool boundary; a paused approval has
    no in-flight side effect and can be cancelled immediately.
    """
    visible_run = get_visible_runtime_run(db, run_id, user)
    if visible_run.kind == "workflow_bridge":
        return request_workflow_cancellation(db, user, run_id=run_id)
    if visible_run.kind != "assistant_turn":
        raise ValueError("Only assistant turns and linked workflow runs can be cancelled")
    if visible_run.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Only the initiating user or an administrator can cancel this run")

    run = get_runtime_run_for_update(db, visible_run.id)
    if run is None:
        raise ValueError("Runtime run not found")
    if run.status in {"succeeded", "failed", "cancelled", "expired", "cancel_requested"}:
        return run
    if run.status in {"awaiting_approval", "awaiting_input"}:
        return cancel_runtime_run(db, run.id, "已取消这次操作。")
    if run.status not in {"queued", "running"}:
        raise ValueError(f"Cannot request cancellation for runtime run in status: {run.status}")

    run.status = "cancel_requested"
    append_events(
        db,
        run.id,
        [
            RuntimeEventDraft(
                type=RuntimeEventType.CAPABILITY_PROGRESSED,
                public_summary="已收到取消请求，将在当前步骤结束后停止。",
                payload={"phase": "cancellation_requested"},
            )
        ],
    )
    db.commit()
    db.refresh(run)
    return run


def runtime_cancellation_requested(db: Session, run_id: str) -> bool:
    """Read the durable cancellation flag without trusting an in-memory Run."""
    return db.scalar(select(RuntimeRun.status).where(RuntimeRun.id == run_id)) == "cancel_requested"


def finalize_requested_runtime_cancellation(
    db: Session,
    run_id: str,
    *,
    message: str = "已取消这次操作。",
) -> RuntimeRun:
    """Close a cooperative assistant cancellation at a safe execution boundary."""
    run = get_runtime_run_for_update(db, run_id)
    if run is None:
        raise ValueError("Runtime run not found")
    if run.status != "cancel_requested":
        return run
    return _finish_runtime_run(
        db,
        run.id,
        message,
        terminal_status="cancelled",
        terminal_event=RuntimeEventType.RUN_CANCELLED,
        terminal_summary="任务已取消。",
        allowed_statuses={"cancel_requested"},
    )


def request_workflow_cancellation(
    db: Session,
    user: CurrentUser,
    *,
    run_id: str,
) -> RuntimeRun:
    """Request cancellation of a workflow bridge at a safe worker boundary.

    A queued or human-paused workflow has no active node and can become
    terminal immediately. A running workflow remains ``cancel_requested``
    until the worker sees the durable request before its next graph node.
    """
    visible_run = get_visible_runtime_run(db, run_id, user)
    if visible_run.kind != "workflow_bridge" or not visible_run.execution_run_id or not visible_run.project_id:
        raise ValueError("Only linked workflow runs can be cancelled through this endpoint")

    require_project_capability(
        db,
        current_user=user,
        project_id=visible_run.project_id,
        capability="workflow.run",
    )

    run = get_runtime_run_for_update(db, visible_run.id)
    if run is None:
        raise ValueError("Runtime run not found")
    if run.status in {"succeeded", "failed", "cancelled", "expired"}:
        return run
    if run.status == "cancel_requested":
        return run

    execution_run = db.get(ExecutionRun, run.execution_run_id)
    if execution_run is None:
        raise ValueError("Linked workflow execution run not found")

    safe_to_cancel_now = execution_run.status in {"queued", "awaiting_human", "awaiting_approval"}
    if safe_to_cancel_now:
        execution_run.status = "cancelled"
        execution_run.finished_at = _now()
        return cancel_runtime_run(db, run.id, "已取消工作流。")

    run.status = "cancel_requested"
    execution_run.status = "cancel_requested"
    append_events(
        db,
        run.id,
        [
            RuntimeEventDraft(
                type=RuntimeEventType.CAPABILITY_PROGRESSED,
                public_summary="已收到取消请求，将在当前步骤结束后停止工作流。",
                payload={"phase": "cancellation_requested"},
            )
        ],
    )
    db.commit()
    db.refresh(run)
    return run


def find_pending_approval_for_conversation(
    db: Session,
    user: CurrentUser,
    conversation_id: str,
) -> RuntimeApproval | None:
    """Return the latest still-actionable approval in a user conversation."""
    while True:
        pending = db.scalar(
            select(RuntimeApproval)
            .join(RuntimeAction, RuntimeApproval.action_id == RuntimeAction.id)
            .join(RuntimeRun, RuntimeAction.run_id == RuntimeRun.id)
            .where(
                RuntimeApproval.status == RuntimeApprovalStatus.PENDING.value,
                RuntimeApproval.user_id == user.id,
                RuntimeApproval.org_id == user.org_id,
                RuntimeRun.conversation_id == conversation_id,
            )
            .order_by(RuntimeApproval.created_at.desc())
        )
        if pending is None:
            return None
        if pending.expires_at > _now():
            return pending
        expire_runtime_approval_if_due(db, approval_id=pending.id)


def _finish_runtime_run(
    db: Session,
    run_id: str,
    message: str,
    *,
    terminal_status: str,
    terminal_event: RuntimeEventType,
    terminal_summary: str,
    allowed_statuses: set[str],
    result_json: dict[str, Any] | None = None,
    error_code: str | None = None,
    parent_event_id: str | None = None,
    message_delta_emitted: bool = False,
    terminal_state: str | None = None,
) -> RuntimeRun:
    safe_message = redact_text(message).strip()
    if not safe_message:
        raise ValueError("Terminal runtime runs require a user-facing message")

    run = get_runtime_run_for_update(db, run_id)
    if run is None:
        raise ValueError("Runtime run not found")
    if run.status == terminal_status:
        return run
    if run.status not in allowed_statuses:
        raise ValueError(f"Cannot finish runtime run in status: {run.status}")

    cancellation_events = _cancel_pending_approvals(db, run) if terminal_status == "cancelled" else []
    persisted_result = dict(result_json or {})
    persisted_result["message"] = safe_message
    run.status = terminal_status
    run.result_json = redact_arguments(persisted_result)
    run.error_code = error_code
    run.error_message = safe_message if error_code else None
    run.finished_at = _now()
    append_events(
        db,
        run.id,
        [
            *cancellation_events,
            RuntimeEventDraft(
                type=RuntimeEventType.MESSAGE_COMPLETED,
                parent_event_id=parent_event_id,
                public_summary=safe_message,
                payload={
                    "message": safe_message,
                    "delta_emitted": message_delta_emitted,
                    "terminal_failure": terminal_event is RuntimeEventType.RUN_FAILED,
                },
            ),
            RuntimeEventDraft(
                type=terminal_event,
                parent_event_id=parent_event_id,
                public_summary=terminal_summary,
                payload={
                    "status": terminal_status,
                    "state": terminal_state
                    or (
                        "failed"
                        if terminal_event is RuntimeEventType.RUN_FAILED
                        else "cancelled"
                        if terminal_event is RuntimeEventType.RUN_CANCELLED
                        else "completed"
                    ),
                    "kind": run.kind,
                    "message_delta_emitted": message_delta_emitted,
                    **({"message": safe_message} if terminal_event is RuntimeEventType.RUN_FAILED else {}),
                    **({"error_code": error_code} if error_code else {}),
                },
            ),
        ],
    )
    db.commit()
    db.refresh(run)
    return run


def _cancel_pending_approvals(db: Session, run: RuntimeRun) -> list[RuntimeEventDraft]:
    """Close approvals before terminal cancellation so they cannot execute later."""
    rows = db.execute(
        select(RuntimeApproval, RuntimeAction)
        .join(RuntimeAction, RuntimeApproval.action_id == RuntimeAction.id)
        .where(
            RuntimeAction.run_id == run.id,
            RuntimeApproval.status == RuntimeApprovalStatus.PENDING.value,
        )
        .with_for_update()
    ).all()
    now = _now()
    events: list[RuntimeEventDraft] = []
    for approval, action in rows:
        approval.status = RuntimeApprovalStatus.CANCELLED.value
        approval.decision_json = {"decision": "cancel"}
        approval.resolved_at = now
        action.status = RuntimeActionStatus.CANCELLED.value
        action.completed_at = now
        events.append(
            RuntimeEventDraft(
                type=RuntimeEventType.APPROVAL_RESOLVED,
                parent_event_id=action.parent_event_id,
                public_summary="已取消待确认操作。",
                payload=_action_event_payload(
                    action,
                    approval_id=approval.id,
                    status=RuntimeApprovalStatus.CANCELLED.value,
                ),
            )
        )
    return events


def expire_runtime_approval_if_due(
    db: Session,
    *,
    approval_id: str,
) -> RuntimeApproval | None:
    """Expire one pending approval and leave a terminal, replayable trace."""
    approval = db.scalar(select(RuntimeApproval).where(RuntimeApproval.id == approval_id).with_for_update())
    if approval is None or approval.status != RuntimeApprovalStatus.PENDING.value:
        return approval
    if approval.expires_at > _now():
        return approval

    action = db.get(RuntimeAction, approval.action_id)
    run = get_runtime_run_for_update(db, action.run_id) if action is not None else None
    if action is None or run is None:
        raise ValueError("Runtime approval action is unavailable")

    message = "审批已过期，未执行该操作。"
    now = _now()
    approval.status = RuntimeApprovalStatus.EXPIRED.value
    approval.resolved_at = now
    action.status = RuntimeActionStatus.EXPIRED.value
    action.completed_at = now
    run.status = "expired"
    run.result_json = redact_arguments({"message": message})
    run.error_code = "approval_expired"
    run.error_message = message
    run.finished_at = now
    append_events(
        db,
        run.id,
        [
            RuntimeEventDraft(
                type=RuntimeEventType.APPROVAL_RESOLVED,
                parent_event_id=action.parent_event_id,
                public_summary=message,
                payload=_action_event_payload(
                    action,
                    approval_id=approval.id,
                    status=RuntimeApprovalStatus.EXPIRED.value,
                ),
            ),
            RuntimeEventDraft(
                type=RuntimeEventType.MESSAGE_COMPLETED,
                parent_event_id=action.parent_event_id,
                public_summary=message,
                payload={"message": message},
            ),
            RuntimeEventDraft(
                type=RuntimeEventType.RUN_FAILED,
                parent_event_id=action.parent_event_id,
                public_summary="任务因审批过期而结束。",
                payload={"status": "expired", "error_code": "approval_expired"},
            ),
        ],
    )
    db.commit()
    db.refresh(approval)
    return approval


def reconcile_runtime_run_for_replay(db: Session, run_id: str) -> RuntimeRun:
    """Resolve durable cancellation or expired approval before replaying a run.

    Browser reconnects must never resurrect a run that was cancelled while its
    stream was disconnected, nor keep presenting an approval that can no
    longer be accepted. This function performs only lifecycle reconciliation;
    adapters remain responsible for rendering the resulting event trace.
    """
    run = db.get(RuntimeRun, run_id)
    if run is None:
        raise ValueError("Runtime run not found")
    if run.status == "cancel_requested":
        return finalize_requested_runtime_cancellation(db, run.id)
    if run.status != "awaiting_approval":
        return run

    approval_ids = list(
        db.scalars(
            select(RuntimeApproval.id)
            .join(RuntimeAction, RuntimeApproval.action_id == RuntimeAction.id)
            .where(
                RuntimeAction.run_id == run.id,
                RuntimeApproval.status == RuntimeApprovalStatus.PENDING.value,
            )
        )
    )
    for approval_id in approval_ids:
        expire_runtime_approval_if_due(db, approval_id=approval_id)
    db.refresh(run)
    return run


def execute_capability(
    db: Session,
    user: CurrentUser,
    *,
    run_id: str,
    capability_name: str,
    arguments: dict[str, Any],
    action_key: str,
    parent_event_id: str | None = None,
    turn_id: str | None = None,
    tool_call_id: str | None = None,
    executor: CapabilityExecutor | None = None,
) -> RuntimeCapabilityExecution:
    """Prepare and execute one capability at most once for an action key.

    Most callers use this convenience boundary. The streaming Harness uses the
    two public lifecycle steps below so it can expose the durable
    ``capability.started`` event before the domain operation begins.
    """
    prepared = prepare_capability_execution(
        db,
        user,
        run_id=run_id,
        capability_name=capability_name,
        arguments=arguments,
        action_key=action_key,
        parent_event_id=parent_event_id,
        turn_id=turn_id,
        tool_call_id=tool_call_id,
    )
    if (
        prepared.approval is not None
        or prepared.action.status != RuntimeActionStatus.PENDING.value
    ):
        return prepared
    return execute_prepared_capability(
        db,
        user,
        action_id=prepared.action.id,
        executor=executor,
    )


def prepare_capability_execution(
    db: Session,
    user: CurrentUser,
    *,
    run_id: str,
    capability_name: str,
    arguments: dict[str, Any],
    action_key: str,
    parent_event_id: str | None = None,
    turn_id: str | None = None,
    tool_call_id: str | None = None,
) -> RuntimeCapabilityExecution:
    """Persist one action and its initial event without running side effects."""
    run = get_visible_runtime_run(db, run_id, user)
    definition = get_capability_definition(capability_name)
    missing_fields = missing_required_capability_arguments(definition.name, arguments)
    if missing_fields:
        raise ValueError(f"{definition.label_zh}缺少必填信息：{'、'.join(missing_fields)}")
    policy = evaluate_policy(definition, approval_mode=run.policy_snapshot_json.get("approval_mode", "risky_only"))

    action = db.scalar(
        select(RuntimeAction)
        .where(RuntimeAction.run_id == run.id, RuntimeAction.action_key == action_key)
        .with_for_update()
    )
    if action is not None:
        return _replay_existing_action(db, action)

    initial_status = (
        RuntimeActionStatus.AWAITING_APPROVAL.value
        if policy.outcome is RuntimePolicyOutcome.REQUIRE_APPROVAL
        else RuntimeActionStatus.PENDING.value
    )
    action = RuntimeAction(
        run_id=run.id,
        parent_event_id=parent_event_id,
        turn_id=turn_id,
        tool_call_id=tool_call_id,
        action_key=action_key,
        capability_name=definition.name,
        status=initial_status,
        risk_level=definition.risk_level.value,
        policy_outcome=policy.outcome.value,
        approval_mode=run.policy_snapshot_json.get("approval_mode", "risky_only"),
        arguments_json=redact_arguments(arguments),
    )
    db.add(action)
    db.commit()
    db.refresh(action)

    publish_event(
        db,
        run.id,
        RuntimeEventDraft(
            type=RuntimeEventType.CAPABILITY_STARTED,
            parent_event_id=action.parent_event_id,
            public_summary=f"正在{definition.label_zh}。",
            payload=_action_event_payload(action, title=definition.label_zh),
        ),
    )

    if policy.outcome is RuntimePolicyOutcome.REQUIRE_APPROVAL:
        approval = _create_pending_approval(
            db,
            run,
            action,
            user,
            format_approval_request(definition.name, arguments),
        )
        return RuntimeCapabilityExecution(action=action, approval=approval)

    if policy.outcome is RuntimePolicyOutcome.DENY:
        action.status = RuntimeActionStatus.DENIED.value
        action.error_code = policy.reason_code
        action.error_message = policy.public_message
        action.completed_at = _now()
        db.commit()
        publish_event(
            db,
            run.id,
            RuntimeEventDraft(
                type=RuntimeEventType.CAPABILITY_FAILED,
                parent_event_id=action.parent_event_id,
                public_summary=policy.public_message,
                payload=_action_event_payload(
                    action,
                    title=definition.label_zh,
                    reason_code=policy.reason_code,
                ),
            ),
        )
        return RuntimeCapabilityExecution(action=action)

    return RuntimeCapabilityExecution(action=action)


def execute_prepared_capability(
    db: Session,
    user: CurrentUser,
    *,
    action_id: str,
    executor: CapabilityExecutor | None = None,
) -> RuntimeCapabilityExecution:
    """Execute a prepared action after its started event is observable."""
    action = db.scalar(select(RuntimeAction).where(RuntimeAction.id == action_id).with_for_update())
    if action is None:
        raise ValueError("Runtime action not found")
    run = get_visible_runtime_run(db, action.run_id, user)
    if action.status != RuntimeActionStatus.PENDING.value:
        return _replay_existing_action(db, action)
    return _execute_action(db, user, run, action, executor)


def resolve_approval(
    db: Session,
    user: CurrentUser,
    *,
    approval_id: str,
    decision: RuntimeApprovalDecisionType,
    edited_arguments: dict[str, Any] | None = None,
    executor: CapabilityExecutor | None = None,
) -> RuntimeCapabilityExecution:
    approval = db.scalar(select(RuntimeApproval).where(RuntimeApproval.id == approval_id).with_for_update())
    if approval is None or approval.user_id != user.id or approval.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="Runtime approval not found")

    action = db.get(RuntimeAction, approval.action_id)
    if action is None:
        raise ValueError("Runtime approval action is unavailable")
    run = get_visible_runtime_run(db, action.run_id, user)

    if approval.status != RuntimeApprovalStatus.PENDING.value:
        raise RuntimeApprovalResolvedError("Approval is no longer pending")
    if approval.expires_at <= _now():
        expire_runtime_approval_if_due(db, approval_id=approval.id)
        raise RuntimeApprovalExpiredError("审批已过期，未执行该操作。")

    if decision is RuntimeApprovalDecisionType.REJECT:
        approval.status = RuntimeApprovalStatus.REJECTED.value
        approval.decision_json = {"decision": decision.value}
        approval.resolved_at = _now()
        action.status = RuntimeActionStatus.DENIED.value
        action.completed_at = _now()
        db.commit()
        publish_event(
            db,
            run.id,
            RuntimeEventDraft(
                type=RuntimeEventType.APPROVAL_RESOLVED,
                parent_event_id=action.parent_event_id,
                public_summary="已拒绝该操作。",
                payload=_action_event_payload(
                    action,
                    approval_id=approval.id,
                    status=RuntimeApprovalStatus.REJECTED.value,
                ),
            ),
        )
        return RuntimeCapabilityExecution(action=action, approval=approval)

    if decision is RuntimeApprovalDecisionType.EDIT:
        if edited_arguments is None:
            raise ValueError("Edited approval requires edited arguments")
        approval.status = RuntimeApprovalStatus.EDITED.value
        approval.decision_json = {"decision": decision.value, "arguments": redact_arguments(edited_arguments)}
        action.arguments_json = redact_arguments(edited_arguments)
    else:
        approval.status = RuntimeApprovalStatus.APPROVED.value
        approval.decision_json = {"decision": decision.value}
    approval.resolved_at = _now()
    action.status = RuntimeActionStatus.PENDING.value
    run.status = "running"
    db.commit()
    publish_event(
        db,
        run.id,
        RuntimeEventDraft(
            type=RuntimeEventType.APPROVAL_RESOLVED,
            parent_event_id=action.parent_event_id,
            public_summary="审批已通过，正在继续执行。",
            payload=_action_event_payload(
                action,
                approval_id=approval.id,
                status=approval.status,
            ),
        ),
    )
    execution = _execute_action(db, user, run, action, executor)
    return RuntimeCapabilityExecution(
        action=execution.action,
        approval=approval,
        result=execution.result,
    )


def _replay_existing_action(db: Session, action: RuntimeAction) -> RuntimeCapabilityExecution:
    approval = db.scalar(select(RuntimeApproval).where(RuntimeApproval.action_id == action.id))
    result = None
    if action.status == RuntimeActionStatus.SUCCEEDED.value:
        result = format_public_result(action.capability_name, action.result_json or {})
    return RuntimeCapabilityExecution(action=action, approval=approval, result=result)


def _expected_confirmation_text(
    db: Session,
    capability_name: str,
    arguments: dict | None,
) -> str | None:
    """Resolve the typed-confirmation string the UI must collect for destructive tools."""
    args = arguments or {}
    if capability_name != "delete_project":
        return None
    # Prefer an explicit name if the model already supplied one.
    explicit = args.get("project_name") or args.get("name") or args.get("confirmation_text")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    project_id = args.get("project_id")
    if not isinstance(project_id, str) or not project_id:
        return None
    from app.models import Project

    project = db.get(Project, project_id)
    if project is None or not isinstance(project.name, str) or not project.name.strip():
        return None
    return project.name.strip()


def _create_pending_approval(
    db: Session,
    run: RuntimeRun,
    action: RuntimeAction,
    user: CurrentUser,
    message: str,
) -> RuntimeApproval:
    definition = get_capability_definition(action.capability_name)
    expected_text = (
        _expected_confirmation_text(db, action.capability_name, action.arguments_json)
        if definition.requires_typed_confirmation
        else None
    )
    if action.capability_name == "delete_project" and expected_text:
        # Make the approval copy explicit: user must retype the project name.
        message = f"删除项目后无法恢复。请输入完整项目名称「{expected_text}」确认继续。"
    approval = RuntimeApproval(
        action_id=action.id,
        user_id=user.id,
        org_id=user.org_id,
        status=RuntimeApprovalStatus.PENDING.value,
        payload_json={
            "capability": action.capability_name,
            "arguments": action.arguments_json,
            "message": message,
            "requires_typed_confirmation": definition.requires_typed_confirmation,
            "expected_text": expected_text,
        },
        expires_at=_now() + timedelta(minutes=30),
    )
    run.status = "awaiting_approval"
    db.add(approval)
    db.commit()
    db.refresh(approval)
    payload = {
        "approval_id": approval.id,
        "capability": action.capability_name,
        "arguments": action.arguments_json,
        "message": message,
        "requires_typed_confirmation": definition.requires_typed_confirmation,
    }
    if expected_text:
        payload["expected_text"] = expected_text
    publish_event(
        db,
        run.id,
        RuntimeEventDraft(
            type=RuntimeEventType.APPROVAL_REQUESTED,
            parent_event_id=action.parent_event_id,
            public_summary="该操作需要你的确认。",
            payload=_action_event_payload(action, **payload),
        ),
    )
    return approval


def _execute_action(
    db: Session,
    user: CurrentUser,
    run: RuntimeRun,
    action: RuntimeAction,
    executor: CapabilityExecutor | None,
) -> RuntimeCapabilityExecution:
    if action.status == RuntimeActionStatus.SUCCEEDED.value:
        return _replay_existing_action(db, action)

    action.status = RuntimeActionStatus.RUNNING.value
    db.commit()
    execute = executor or _legacy_executor(action.capability_name)
    try:
        execution_arguments = dict(action.arguments_json or {})
        if action.capability_name in {
            "start_draft_section",
            "start_redraft_section",
            "run_section_campaign",
            "start_deep_research",
            "fetch_url_to_project",
        }:
            execution_arguments.setdefault("parent_runtime_run_id", run.id)
        raw_result = execute(db, user, execution_arguments)
        public_result = format_public_result(action.capability_name, raw_result)
        public_result = PublicCapabilityResult(
            public_result.summary,
            public_result.payload,
            observation_payload=redact_arguments(raw_result),
        )
    except Exception as exc:
        failure = classify_capability_failure(exc)
        logger.warning(
            "Runtime capability execution failed: run_id=%s capability=%s error_type=%s error_code=%s",
            run.id,
            action.capability_name,
            type(exc).__name__,
            failure.error_code,
        )
        action.status = RuntimeActionStatus.FAILED.value
        action.error_code = failure.error_code
        action.error_message = failure.message
        action.completed_at = _now()
        _record_runtime_action_audit(
            db,
            run=run,
            action=action,
            actor_id=user.id,
            outcome="failed",
        )
        db.commit()
        publish_event(
            db,
            run.id,
            RuntimeEventDraft(
                type=RuntimeEventType.CAPABILITY_FAILED,
                parent_event_id=action.parent_event_id,
                public_summary=failure.message,
                payload=_action_event_payload(
                    action,
                    title=get_capability_definition(action.capability_name).label_zh,
                    reason_code=action.error_code,
                ),
            ),
        )
        raise

    action.status = RuntimeActionStatus.SUCCEEDED.value
    action.result_json = redact_arguments(raw_result)
    action.public_summary = public_result.summary
    action.error_code = None
    action.error_message = None
    action.completed_at = _now()
    _record_runtime_action_audit(
        db,
        run=run,
        action=action,
        actor_id=user.id,
        outcome="succeeded",
        raw_result=raw_result,
    )
    db.commit()
    publish_event(
        db,
        run.id,
        RuntimeEventDraft(
            type=RuntimeEventType.CAPABILITY_SUCCEEDED,
            parent_event_id=action.parent_event_id,
            public_summary=public_result.summary,
            # A capability result may include a domain ``title`` (for example,
            # a newly-created deliverable). Keep that value unchanged.
            payload=_action_event_payload(action, **public_result.payload),
        ),
    )
    return RuntimeCapabilityExecution(action=action, result=public_result)


def _record_runtime_action_audit(
    db: Session,
    *,
    run: RuntimeRun,
    action: RuntimeAction,
    actor_id: str,
    outcome: str,
    raw_result: dict[str, Any] | None = None,
) -> None:
    """Persist only correlation metadata for a project-scoped runtime action.

    The action itself retains redacted operational state.  The project audit
    trail is deliberately narrower: it exists to join a user-visible project
    change to its durable RuntimeRun without duplicating arguments, results,
    provider output, or exception text.
    """
    project_id = run.project_id
    if project_id is None and action.capability_name == "create_project":
        candidate_id = (raw_result or {}).get("id")
        if isinstance(candidate_id, str):
            project = db.get(Project, candidate_id)
            if project is not None and project.org_id == run.org_id:
                project_id = project.id
    if project_id is None:
        return

    payload: dict[str, str] = {
        "runtime_run_id": run.id,
        "trace_id": run.trace_id,
        "runtime_action_id": action.id,
        "capability": action.capability_name,
        "status": outcome,
    }
    if outcome == "failed" and action.error_code:
        payload["error_code"] = action.error_code
    record_audit_event(
        db,
        project_id=project_id,
        event_type=f"runtime.capability.{outcome}",
        actor_type="user",
        actor_id=actor_id,
        payload=payload,
    )


def _legacy_executor(capability_name: str) -> CapabilityExecutor:
    def execute(db: Session, user: CurrentUser, arguments: dict[str, Any]) -> dict[str, Any]:
        from app.assistant.tools import execute_tool

        return execute_tool(db, user, capability_name, arguments).result

    return execute


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
