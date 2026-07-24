"""Idempotent capability execution and durable approval lifecycle."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assistant.audit import redact_arguments, redact_text
from app.access.service import require_project_capability
from app.auth.schemas import CurrentUser
from app.models import ExecutionRun, RuntimeAction, RuntimeApproval, RuntimeRun
from contracts.runtime import (
    RuntimeActionStatus,
    RuntimeApprovalDecisionType,
    RuntimeApprovalStatus,
    RuntimeEventType,
    RuntimePolicyOutcome,
)

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


def list_runtime_runs_query(
    db: Session,
    current_user: CurrentUser,
    *,
    limit: int = 50,
    conversation_id: str | None = None,
) -> list[RuntimeRunListRow]:
    """Return a bounded, permission-scoped list for the Run Center / history restore."""

    return list_visible_runtime_runs(
        db,
        current_user=current_user,
        limit=max(1, min(limit, 100)),
        conversation_id=conversation_id,
    )


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
    commit: bool = True,
) -> RuntimeRun:
    """Create one visible runtime run, or return the caller's prior idempotent run."""
    if approval_mode not in {"request_approval", "risky_only", "full_access", "custom"}:
        raise ValueError(f"Invalid approval mode: {approval_mode}")
    if project_id is not None:
        require_project_capability(
            db,
            current_user=user,
            project_id=project_id,
            capability="project.read",
        )
    if idempotency_key:
        existing = db.scalar(
            select(RuntimeRun).where(
                RuntimeRun.org_id == user.org_id,
                RuntimeRun.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.user_id != user.id:
                raise HTTPException(status_code=409, detail="Idempotency key is already in use")
            return existing

    run = RuntimeRun(
        kind=kind,
        status="running",
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
    db.add(run)
    db.flush()
    started_event = RuntimeEventDraft(
        type=RuntimeEventType.RUN_STARTED,
        public_summary="任务已开始。",
        payload={"kind": run.kind, "engine": run.engine},
    )
    if commit:
        db.commit()
        db.refresh(run)
        publish_event(db, run.id, started_event)
    else:
        append_events(db, run.id, [started_event])
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


def complete_runtime_run(
    db: Session,
    run_id: str,
    message: str,
    *,
    result_json: dict[str, Any] | None = None,
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
    )


def fail_runtime_run(
    db: Session,
    run_id: str,
    message: str,
    *,
    error_code: str = "runtime_failed",
    result_json: dict[str, Any] | None = None,
) -> RuntimeRun:
    """Record a safe terminal failure without leaking provider or tool details."""
    return _finish_runtime_run(
        db,
        run_id,
        message,
        terminal_status="failed",
        terminal_event=RuntimeEventType.RUN_FAILED,
        terminal_summary="任务未能完成。",
        allowed_statuses={"queued", "running", "awaiting_approval", "cancel_requested"},
        result_json=result_json,
        error_code=error_code,
    )


def cancel_runtime_run(db: Session, run_id: str, message: str = "已取消这次操作。") -> RuntimeRun:
    """Persist a user-requested cancellation and its terminal evidence."""
    return _finish_runtime_run(
        db,
        run_id,
        message,
        terminal_status="cancelled",
        terminal_event=RuntimeEventType.RUN_CANCELLED,
        terminal_summary="任务已取消。",
        allowed_statuses={"queued", "running", "awaiting_approval", "cancel_requested"},
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
    return db.scalar(
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
            RuntimeEventDraft(
                type=RuntimeEventType.MESSAGE_COMPLETED,
                public_summary=safe_message,
                payload={"message": safe_message},
            ),
            RuntimeEventDraft(
                type=terminal_event,
                public_summary=terminal_summary,
                payload={"status": terminal_status, **({"error_code": error_code} if error_code else {})},
            ),
        ],
    )
    db.commit()
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
    executor: CapabilityExecutor | None = None,
) -> RuntimeCapabilityExecution:
    """Execute one capability at most once for a runtime action key."""
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
            public_summary=f"正在{definition.label_zh}。",
            payload={"capability": definition.name},
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
                public_summary=policy.public_message,
                payload={"capability": definition.name, "reason_code": policy.reason_code},
            ),
        )
        return RuntimeCapabilityExecution(action=action)

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
        approval.status = RuntimeApprovalStatus.EXPIRED.value
        approval.resolved_at = _now()
        action.status = RuntimeActionStatus.EXPIRED.value
        action.completed_at = _now()
        run.status = "expired"
        db.commit()
        publish_event(
            db,
            run.id,
            RuntimeEventDraft(
                type=RuntimeEventType.APPROVAL_RESOLVED,
                public_summary="审批已过期，未执行该操作。",
                payload={
                    "approval_id": approval.id,
                    "capability": action.capability_name,
                    "status": RuntimeApprovalStatus.EXPIRED.value,
                },
            ),
        )
        raise RuntimeApprovalExpiredError("Approval has expired")

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
                public_summary="已拒绝该操作。",
                payload={
                    "approval_id": approval.id,
                    "capability": action.capability_name,
                    "status": RuntimeApprovalStatus.REJECTED.value,
                },
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
            public_summary="审批已通过，正在继续执行。",
            payload={
                "approval_id": approval.id,
                "capability": action.capability_name,
                "status": approval.status,
            },
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
            public_summary="该操作需要你的确认。",
            payload=payload,
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
        if action.capability_name in {"start_draft_section", "start_redraft_section"}:
            execution_arguments.setdefault("parent_runtime_run_id", run.id)
        raw_result = execute(db, user, execution_arguments)
        public_result = format_public_result(action.capability_name, raw_result)
    except Exception as exc:
        safe_error = redact_text(str(exc))
        action.status = RuntimeActionStatus.FAILED.value
        action.error_code = "capability_execution_failed"
        action.error_message = safe_error
        action.completed_at = _now()
        db.commit()
        publish_event(
            db,
            run.id,
            RuntimeEventDraft(
                type=RuntimeEventType.CAPABILITY_FAILED,
                public_summary="操作未能完成。",
                payload={"capability": action.capability_name, "reason_code": action.error_code},
            ),
        )
        raise

    action.status = RuntimeActionStatus.SUCCEEDED.value
    action.result_json = redact_arguments(raw_result)
    action.public_summary = public_result.summary
    action.error_code = None
    action.error_message = None
    action.completed_at = _now()
    db.commit()
    publish_event(
        db,
        run.id,
        RuntimeEventDraft(
            type=RuntimeEventType.CAPABILITY_SUCCEEDED,
            public_summary=public_result.summary,
            payload={"capability": action.capability_name, **public_result.payload},
        ),
    )
    return RuntimeCapabilityExecution(action=action, result=public_result)


def _legacy_executor(capability_name: str) -> CapabilityExecutor:
    def execute(db: Session, user: CurrentUser, arguments: dict[str, Any]) -> dict[str, Any]:
        from app.assistant.tools import execute_tool

        return execute_tool(db, user, capability_name, arguments).result

    return execute


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
