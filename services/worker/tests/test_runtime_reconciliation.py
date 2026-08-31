from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

from app.db import SessionLocal
from app.execution.runtime_reconciliation import reconcile_runtime_runs
from app.models import (
    ChatConversation,
    ChatTaskState,
    Organization,
    RuntimeAction,
    RuntimeApproval,
    RuntimeEvent,
    RuntimeRun,
    TaskOutboxEvent,
    User,
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


def _run(
    db,
    *,
    kind: str = "assistant_turn",
    status: str = "running",
    created_at: datetime,
) -> RuntimeRun:
    suffix = uuid.uuid4().hex[:10]
    organization = Organization(slug=f"reconcile-{suffix}", name="Reconciliation Test Organization")
    db.add(organization)
    db.flush()
    user = User(
        org_id=organization.id,
        email=f"reconcile-{suffix}@example.test",
        display_name="Reconciliation Test",
        role="admin",
        password_hash="test-only",
    )
    db.add(user)
    db.flush()
    conversation = ChatConversation(user_id=user.id, title="Reconciliation")
    db.add(conversation)
    db.flush()
    run = RuntimeRun(
        kind=kind,
        status=status,
        org_id=organization.id,
        user_id=user.id,
        conversation_id=conversation.id,
        engine="pi" if kind == "assistant_turn" else "workflow_worker",
        trace_id=f"trace-{suffix}",
        policy_snapshot_json={},
        created_at=created_at,
    )
    db.add(run)
    db.flush()
    return run


def _outbox(db, run: RuntimeRun, *, status: str, lease_expires_at: datetime | None) -> None:
    db.add(
        TaskOutboxEvent(
            org_id=run.org_id,
            project_id=run.project_id,
            execution_run_id=run.execution_run_id,
            runtime_run_id=run.id,
            task_name="worker.run_assistant_turn",
            args_json=[run.id],
            kwargs_json={},
            deduplication_key=f"reconcile:{run.id}",
            status=status,
            lease_expires_at=lease_expires_at,
            created_at=run.created_at,
        )
    )


def _events(db, run_id: str) -> list[str]:
    return [
        event.event_type
        for event in db.query(RuntimeEvent)
        .filter(RuntimeEvent.run_id == run_id)
        .order_by(RuntimeEvent.sequence.asc())
        .all()
    ]


def test_reconciliation_fails_an_old_assistant_run_without_outbox() -> None:
    current = _now()
    db = SessionLocal()
    try:
        run = _run(db, created_at=current - timedelta(hours=2))
        run_id = run.id
        db.commit()
    finally:
        db.close()

    result = reconcile_runtime_runs(now=current)

    db = SessionLocal()
    try:
        persisted = db.get(RuntimeRun, run_id)
        assert persisted is not None
        assert persisted.status == "failed"
        assert persisted.error_code == "assistant_run_orphaned"
        assert persisted.finished_at is not None
        assert _events(db, run_id) == ["run.failed"]
        assert int(result["failed"]) >= 1
    finally:
        db.close()


def test_reconciliation_preserves_a_run_with_a_live_outbox_lease() -> None:
    current = _now()
    db = SessionLocal()
    try:
        run = _run(db, created_at=current - timedelta(hours=2))
        _outbox(db, run, status="processing", lease_expires_at=current + timedelta(minutes=5))
        run_id = run.id
        db.commit()
    finally:
        db.close()

    reconcile_runtime_runs(now=current)

    db = SessionLocal()
    try:
        persisted = db.get(RuntimeRun, run_id)
        assert persisted is not None
        assert persisted.status == "running"
    finally:
        db.close()


def test_reconciliation_closes_a_cancel_request_without_a_worker_lease() -> None:
    current = _now()
    db = SessionLocal()
    try:
        run = _run(db, status="cancel_requested", created_at=current - timedelta(minutes=20))
        run_id = run.id
        db.commit()
    finally:
        db.close()

    result = reconcile_runtime_runs(now=current)

    db = SessionLocal()
    try:
        persisted = db.get(RuntimeRun, run_id)
        assert persisted is not None
        assert persisted.status == "cancelled"
        assert _events(db, run_id) == ["run.cancelled"]
        assert int(result["cancelled"]) >= 1
    finally:
        db.close()


def test_reconciliation_expires_due_approval_and_preserves_terminal_trace() -> None:
    current = _now()
    db = SessionLocal()
    try:
        run = _run(db, status="awaiting_approval", created_at=current - timedelta(hours=2))
        action = RuntimeAction(
            run_id=run.id,
            action_key="reconcile-approval",
            capability_name="create_project",
            status="awaiting_approval",
            risk_level="low_risk_write",
            policy_outcome="require_approval",
            approval_mode="risky_only",
            arguments_json={},
        )
        db.add(action)
        db.flush()
        approval = RuntimeApproval(
            action_id=action.id,
            user_id=run.user_id,
            org_id=run.org_id,
            status="pending",
            payload_json={},
            expires_at=current - timedelta(minutes=1),
        )
        db.add(approval)
        db.flush()
        run_id = run.id
        approval_id = approval.id
        action_id = action.id
        db.commit()
    finally:
        db.close()

    result = reconcile_runtime_runs(now=current)

    db = SessionLocal()
    try:
        persisted_run = db.get(RuntimeRun, run_id)
        persisted_approval = db.get(RuntimeApproval, approval_id)
        persisted_action = db.get(RuntimeAction, action_id)
        assert persisted_run is not None and persisted_run.status == "expired"
        assert persisted_approval is not None and persisted_approval.status == "expired"
        assert persisted_action is not None and persisted_action.status == "expired"
        assert _events(db, run_id) == ["approval.resolved", "message.completed", "run.failed"]
        assert int(result["expired_approvals"]) >= 1
    finally:
        db.close()


def test_reconciliation_expires_stale_missing_input_and_keeps_recent_input() -> None:
    current = _now()
    db = SessionLocal()
    try:
        stale_run = _run(db, status="awaiting_input", created_at=current - timedelta(hours=2))
        stale_state = ChatTaskState(
            conversation_id=stale_run.conversation_id,
            status="needs_input",
            tool_name="create_project",
            arguments_json={},
            missing_fields_json={"fields": ["name"]},
            updated_at=current - timedelta(hours=1),
        )
        db.add(stale_state)
        recent_run = _run(db, status="awaiting_input", created_at=current - timedelta(hours=2))
        recent_state = ChatTaskState(
            conversation_id=recent_run.conversation_id,
            status="needs_input",
            tool_name="create_project",
            arguments_json={},
            missing_fields_json={"fields": ["name"]},
            updated_at=current - timedelta(minutes=5),
        )
        db.add(recent_state)
        stale_run_id = stale_run.id
        recent_run_id = recent_run.id
        recent_conversation_id = recent_run.conversation_id
        db.commit()
    finally:
        db.close()

    result = reconcile_runtime_runs(now=current)

    db = SessionLocal()
    try:
        stale_persisted = db.get(RuntimeRun, stale_run_id)
        recent_persisted = db.get(RuntimeRun, recent_run_id)
        assert stale_persisted is not None and stale_persisted.status == "failed"
        assert recent_persisted is not None and recent_persisted.status == "awaiting_input"
        assert db.get(ChatTaskState, recent_conversation_id) is not None
        assert int(result["failed"]) >= 1
    finally:
        db.close()
