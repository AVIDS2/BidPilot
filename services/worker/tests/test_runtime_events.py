"""Worker-side persistence tests for runtime progress events."""

from __future__ import annotations

import uuid

from contracts.models import Notification, Organization, RuntimeEvent, RuntimeRun, User
from contracts.runtime import RuntimeEventType

from app.db import SessionLocal
from app.runtime.events import (
    cancel_runtime_run,
    complete_runtime_run,
    is_runtime_cancellation_requested,
    publish_human_approval_requested,
    publish_node_failed,
    publish_provider_retry,
    publish_runtime_event,
)


def _runtime_run() -> RuntimeRun:
    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:10]
        org = Organization(slug=f"worker-runtime-{suffix}", name="Worker Runtime Test")
        db.add(org)
        db.flush()
        user = User(
            org_id=org.id,
            email=f"worker-runtime-{suffix}@example.test",
            display_name="Worker Runtime",
            role="admin",
            password_hash="test-only",
        )
        db.add(user)
        db.flush()
        run = RuntimeRun(
            kind="workflow_bridge",
            status="running",
            org_id=org.id,
            user_id=user.id,
            engine="langgraph_workflow",
            trace_id=f"trace-{suffix}",
            policy_snapshot_json={"approval_mode": "risky_only"},
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
    finally:
        db.close()


def test_worker_runtime_events_are_ordered_redacted_and_terminal() -> None:
    run = _runtime_run()

    publish_runtime_event(
        run.id,
        RuntimeEventType.CAPABILITY_STARTED,
        "正在执行章节起草。",
        {"capability": "section_drafter", "api_key": "sk-never-persist"},
    )
    publish_human_approval_requested(run.id, section_key="technical-approach", review_score=0.91)
    publish_human_approval_requested(run.id, section_key="technical-approach", review_score=0.91)
    complete_runtime_run(run.id, result={"section_key": "technical-approach"})

    db = SessionLocal()
    try:
        db.expire_all()
        refreshed = db.get(RuntimeRun, run.id)
        assert refreshed is not None
        assert refreshed.status == "succeeded"
        events = list(
            db.query(RuntimeEvent)
            .filter(RuntimeEvent.run_id == run.id)
            .order_by(RuntimeEvent.sequence.asc())
            .all()
        )
        assert [(event.sequence, event.event_type) for event in events] == [
            (1, "capability.started"),
            (2, "approval.requested"),
            (3, "run.completed"),
        ]
        assert events[0].payload_json["api_key"] == "***redacted***"
    finally:
        db.close()


def test_worker_terminal_transition_commits_one_durable_wake_notification() -> None:
    run = _runtime_run()

    complete_runtime_run(run.id, result={"section_key": "technical-approach"})
    complete_runtime_run(run.id, result={"section_key": "technical-approach"})

    db = SessionLocal()
    try:
        notifications = list(
            db.query(Notification)
            .filter(Notification.user_id == run.user_id, Notification.type == "agent_task")
            .all()
        )
        assert len(notifications) == 1
        assert notifications[0].link == f"/agent?wake={run.id}"
        assert notifications[0].body == "工作流已完成。\n章节：technical-approach"
        assert db.query(RuntimeEvent).filter(RuntimeEvent.run_id == run.id).count() == 1
    finally:
        db.close()


def test_worker_observes_and_finishes_a_runtime_cancellation_request() -> None:
    run = _runtime_run()
    db = SessionLocal()
    try:
        persisted = db.get(RuntimeRun, run.id)
        assert persisted is not None
        persisted.status = "cancel_requested"
        db.commit()
    finally:
        db.close()

    assert is_runtime_cancellation_requested(run.id)
    cancel_runtime_run(run.id)

    db = SessionLocal()
    try:
        persisted = db.get(RuntimeRun, run.id)
        assert persisted is not None
        assert persisted.status == "cancelled"
        events = list(
            db.query(RuntimeEvent)
            .filter(RuntimeEvent.run_id == run.id)
            .order_by(RuntimeEvent.sequence.asc())
            .all()
        )
        assert [(event.sequence, event.event_type) for event in events] == [(1, "run.cancelled")]
    finally:
        db.close()


def test_provider_retry_event_uses_safe_structured_progress() -> None:
    run = _runtime_run()

    publish_provider_retry(
        run.id,
        node_name="section_drafter",
        error_code="provider_rate_limited",
        next_attempt=2,
        max_attempts=3,
    )

    db = SessionLocal()
    try:
        event = db.query(RuntimeEvent).filter(RuntimeEvent.run_id == run.id).one()
        assert event.event_type == "capability.progressed"
        assert event.public_summary == "模型服务暂时不可用，正在重试。"
        assert event.payload_json == {
            "capability": "section_drafter",
            "node": "section_drafter",
            "phase": "provider_retry",
            "error_code": "provider_rate_limited",
            "next_attempt": 2,
            "max_attempts": 3,
        }
    finally:
        db.close()


def test_node_failure_persists_a_stable_code_without_exception_text() -> None:
    run = _runtime_run()

    publish_node_failed(
        run.id,
        "section_drafter",
        "Authorization: Bearer should-not-appear",
        error_code="provider_auth_failed",
    )

    db = SessionLocal()
    try:
        event = db.query(RuntimeEvent).filter(RuntimeEvent.run_id == run.id).one()
        assert event.event_type == "capability.failed"
        assert event.public_summary == "工作流步骤未能完成。"
        assert event.payload_json == {
            "capability": "section_drafter",
            "node": "section_drafter",
            "error_code": "provider_auth_failed",
        }
    finally:
        db.close()
