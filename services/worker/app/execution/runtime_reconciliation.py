"""Reconcile durable runtime rows that no longer have executable work."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import ChatTaskState, RuntimeAction, RuntimeApproval, RuntimeEvent, RuntimeRun, TaskOutboxEvent
from app.runtime.events import cancel_runtime_run, fail_runtime_run, redact_payload
from contracts.runtime import RuntimeEventType, RuntimeRunStatus


_ACTIVE_STATUSES = {
    RuntimeRunStatus.QUEUED.value,
    RuntimeRunStatus.RUNNING.value,
    RuntimeRunStatus.AWAITING_APPROVAL.value,
    RuntimeRunStatus.AWAITING_INPUT.value,
    RuntimeRunStatus.CANCEL_REQUESTED.value,
}
_TERMINAL_OUTBOX_STATUSES = {"completed", "failed", "cancelled"}
_OUTBOX_LEASE_GRACE = timedelta(hours=1)
_ASSISTANT_STALE_AFTER = timedelta(minutes=30)
_CANCEL_STALE_AFTER = timedelta(minutes=10)
_WORKFLOW_STALE_AFTER = timedelta(hours=1)
_INPUT_STALE_AFTER = timedelta(minutes=30)


def _now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(UTC)
    return current.astimezone(UTC).replace(tzinfo=None) if current.tzinfo else current


def _has_live_outbox(rows: list[TaskOutboxEvent], current: datetime) -> bool:
    for row in rows:
        if row.status in _TERMINAL_OUTBOX_STATUSES:
            continue
        if row.status == "pending":
            return True
        if row.lease_expires_at is None:
            return True
        if row.lease_expires_at > current - _OUTBOX_LEASE_GRACE:
            return True
    return False


def _action_event_payload(action: RuntimeAction, *, approval_id: str, status: str) -> dict[str, str]:
    payload = {
        "capability": action.capability_name,
        "action_id": action.id,
        "approval_id": approval_id,
        "status": status,
    }
    if action.turn_id:
        payload["turn_id"] = action.turn_id
    if action.tool_call_id:
        payload["tool_call_id"] = action.tool_call_id
    return payload


def _expire_approval(db, approval_id: str, current: datetime) -> bool:
    approval = db.scalar(
        select(RuntimeApproval).where(RuntimeApproval.id == approval_id).with_for_update()
    )
    if approval is None or approval.status != "pending" or approval.expires_at > current:
        return False

    action = db.get(RuntimeAction, approval.action_id)
    run = get_runtime_run_for_update(db, action.run_id) if action is not None else None
    if action is None or run is None:
        return False

    message = "审批已过期，未执行该操作。"
    approval.status = "expired"
    approval.decision_json = {"decision": "expire", "source": "runtime_reconciliation"}
    approval.resolved_at = current
    action.status = "expired"
    action.completed_at = current
    if run.status in _ACTIVE_STATUSES:
        run.status = "expired"
        run.result_json = redact_payload({"message": message})
        run.error_code = "approval_expired"
        run.error_message = message
        run.finished_at = current

        latest = db.scalar(select(func.max(RuntimeEvent.sequence)).where(RuntimeEvent.run_id == run.id)) or 0
        db.add_all(
            [
                RuntimeEvent(
                    run_id=run.id,
                    sequence=latest + 1,
                    event_type=RuntimeEventType.APPROVAL_RESOLVED.value,
                    public_summary=message,
                    payload_json=_action_event_payload(
                        action,
                        approval_id=approval.id,
                        status="expired",
                    ),
                ),
                RuntimeEvent(
                    run_id=run.id,
                    sequence=latest + 2,
                    event_type=RuntimeEventType.MESSAGE_COMPLETED.value,
                    public_summary=message,
                    payload_json={"message": message},
                ),
                RuntimeEvent(
                    run_id=run.id,
                    sequence=latest + 3,
                    event_type=RuntimeEventType.RUN_FAILED.value,
                    public_summary="任务因审批过期而结束。",
                    payload_json={"status": "expired", "error_code": "approval_expired"},
                ),
            ]
        )
    db.commit()
    return True


def get_runtime_run_for_update(db, run_id: str) -> RuntimeRun | None:
    return db.scalar(select(RuntimeRun).where(RuntimeRun.id == run_id).with_for_update())


def _stale_after(run: RuntimeRun) -> timedelta:
    if run.status == RuntimeRunStatus.CANCEL_REQUESTED.value:
        return _CANCEL_STALE_AFTER
    if run.status == RuntimeRunStatus.AWAITING_INPUT.value:
        return _INPUT_STALE_AFTER
    if run.kind == "assistant_turn":
        return _ASSISTANT_STALE_AFTER
    return _WORKFLOW_STALE_AFTER


def _orphan_message(kind: str) -> tuple[str, str]:
    if kind == "assistant_turn":
        return "助手运行没有取得执行任务，已自动结束。请重新发送。", "assistant_run_orphaned"
    return "后台工作没有取得执行任务，已自动结束。请重新运行。", "runtime_run_orphaned"


def reconcile_runtime_runs(
    *,
    now: datetime | None = None,
    batch_size: int = 200,
) -> dict[str, str]:
    """Expire due approvals and close orphaned runs without deleting evidence."""

    current = _now(now)
    expired_approvals = 0
    db = SessionLocal()
    try:
        approval_ids = list(
            db.scalars(
                select(RuntimeApproval.id)
                .where(
                    RuntimeApproval.status == "pending",
                    RuntimeApproval.expires_at <= current,
                )
                .order_by(RuntimeApproval.expires_at.asc())
                .limit(batch_size)
            )
        )
    finally:
        db.close()

    for approval_id in approval_ids:
        db = SessionLocal()
        try:
            if _expire_approval(db, approval_id, current):
                expired_approvals += 1
        finally:
            db.close()

    db = SessionLocal()
    candidates: list[tuple[str, str, str]] = []
    scanned = 0
    try:
        runs = list(
            db.scalars(
                select(RuntimeRun)
                .where(RuntimeRun.status.in_(_ACTIVE_STATUSES))
                .order_by(RuntimeRun.created_at.asc())
                .limit(batch_size)
            )
        )
        scanned = len(runs)
        for run in runs:
            created_at = run.created_at or current
            if current - created_at < _stale_after(run):
                continue
            outbox_rows = list(
                db.scalars(
                    select(TaskOutboxEvent).where(TaskOutboxEvent.runtime_run_id == run.id)
                )
            )
            if _has_live_outbox(outbox_rows, current):
                continue
            if run.status == RuntimeRunStatus.AWAITING_APPROVAL.value:
                pending_approval = db.scalar(
                    select(RuntimeApproval.id)
                    .join(RuntimeAction, RuntimeApproval.action_id == RuntimeAction.id)
                    .where(
                        RuntimeAction.run_id == run.id,
                        RuntimeApproval.status == "pending",
                    )
                    .limit(1)
                )
                if pending_approval:
                    continue
            if run.status == RuntimeRunStatus.AWAITING_INPUT.value and run.conversation_id:
                task_state = db.get(ChatTaskState, run.conversation_id)
                if (
                    task_state is not None
                    and task_state.status == "needs_input"
                    and task_state.updated_at is not None
                ):
                    if current - task_state.updated_at < _INPUT_STALE_AFTER:
                        continue
                    db.delete(task_state)
                    db.commit()
            candidates.append((run.id, run.status, run.kind))
    finally:
        db.close()

    cancelled = 0
    failed = 0
    for run_id, status, kind in candidates:
        try:
            if status == RuntimeRunStatus.CANCEL_REQUESTED.value:
                cancel_runtime_run(run_id)
                cancelled += 1
            else:
                message, error_code = _orphan_message(kind)
                fail_runtime_run(run_id, message, error_code=error_code)
                failed += 1
        except (ValueError, RuntimeError):
            # A live worker or a user action may have terminalized the row after
            # the candidate scan. The next pass will observe its new state.
            continue

    return {
        "status": "ok",
        "scanned": str(scanned),
        "expired_approvals": str(expired_approvals),
        "cancelled": str(cancelled),
        "failed": str(failed),
    }


__all__ = ["reconcile_runtime_runs"]
