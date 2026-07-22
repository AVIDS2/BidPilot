from __future__ import annotations

import uuid

import pytest

from app.execution.task_outbox import (
    claim_workflow_task_delivery,
    complete_workflow_task_delivery,
    dispatch_task_outbox_event,
    recover_pending_task_outbox_events,
)
from app.models import ExecutionRun, Organization, Project, TaskOutboxEvent
from app.tasks import draft_section
from contracts.task_outbox import create_task_outbox_event


def _create_workflow_event(db) -> TaskOutboxEvent:
    suffix = uuid.uuid4().hex[:8]
    organization = Organization(slug=f"outbox-{suffix}", name="Outbox Test Organization")
    db.add(organization)
    db.flush()
    project = Project(
        org_id=organization.id,
        name="Outbox Test Project",
        slug=f"outbox-project-{suffix}",
        scenario_package="bidpilot",
    )
    db.add(project)
    db.flush()
    run = ExecutionRun(project_id=project.id, run_type="draft_section", status="queued")
    db.add(run)
    db.flush()
    event = create_task_outbox_event(
        db,
        org_id=organization.id,
        project_id=project.id,
        execution_run_id=run.id,
        runtime_run_id=None,
        task_name="worker.draft_section",
        args=[run.id, project.id, "technical-approach"],
        kwargs={"runtime_run_id": "runtime-test"},
        deduplication_key=f"workflow-run:{run.id}",
    )
    db.commit()
    return event


def test_outbox_dispatches_once_and_consumer_lease_rejects_duplicate_delivery(monkeypatch) -> None:
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        event = _create_workflow_event(db)
        event_id = event.id
        expected_args = list(event.args_json)
    finally:
        db.close()

    published: list[dict] = []
    monkeypatch.setattr(
        "app.execution.task_outbox._send_task",
        lambda name, args, kwargs, task_id: published.append(
            {"name": name, "args": args, "kwargs": kwargs, "task_id": task_id}
        ),
    )

    result = dispatch_task_outbox_event(event_id)

    assert result == {"status": "dispatched", "event_id": event_id}
    assert len(published) == 1
    assert published[0] == {
        "name": "worker.draft_section",
        "args": expected_args,
        "kwargs": {"runtime_run_id": "runtime-test", "outbox_event_id": event_id},
        "task_id": f"outbox:{event_id}",
    }
    assert claim_workflow_task_delivery(event_id) is True
    assert claim_workflow_task_delivery(event_id) is False
    complete_workflow_task_delivery(event_id)

    db = SessionLocal()
    try:
        event = db.get(TaskOutboxEvent, event_id)
        assert event is not None
        assert event.status == "completed"
        assert event.dispatch_attempts == 1
        assert event.delivery_attempts == 1
    finally:
        db.close()


def test_outbox_create_returns_the_existing_event_for_the_same_logical_delivery() -> None:
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        event = _create_workflow_event(db)
        duplicate = create_task_outbox_event(
            db,
            org_id=event.org_id,
            project_id=event.project_id,
            execution_run_id=event.execution_run_id,
            runtime_run_id=event.runtime_run_id,
            task_name=event.task_name,
            args=list(event.args_json),
            kwargs=dict(event.kwargs_json),
            deduplication_key=event.deduplication_key,
        )

        assert duplicate.id == event.id
        assert db.query(TaskOutboxEvent).filter_by(org_id=event.org_id).count() == 1
    finally:
        db.close()


def test_outbox_recovery_dispatches_a_committed_pending_event(monkeypatch) -> None:
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        event_id = _create_workflow_event(db).id
    finally:
        db.close()

    monkeypatch.setattr(
        "app.execution.task_outbox.list_dispatchable_task_outbox_event_ids",
        lambda _db, *, limit: [event_id],
    )
    monkeypatch.setattr("app.execution.task_outbox._send_task", lambda *_args, **_kwargs: None)

    result = recover_pending_task_outbox_events(batch_size=1)

    assert result == {"status": "ok", "scanned": "1", "dispatched": "1", "pending": "0", "failed": "0"}


def test_outbox_marks_failed_when_workflow_task_raises(monkeypatch) -> None:
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        event = _create_workflow_event(db)
        event_id = event.id
        run_id, project_id, section_key = event.args_json
    finally:
        db.close()

    monkeypatch.setattr("app.execution.task_outbox._send_task", lambda *_args, **_kwargs: None)
    dispatch_task_outbox_event(event_id)
    monkeypatch.setattr(
        "app.tasks._execute_draft_section",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("test workflow failure")),
    )

    with pytest.raises(RuntimeError, match="test workflow failure"):
        draft_section(run_id, project_id, section_key, outbox_event_id=event_id)

    db = SessionLocal()
    try:
        event = db.get(TaskOutboxEvent, event_id)
        assert event is not None
        assert event.status == "failed"
        assert event.last_error_code == "workflow_task_exception"
    finally:
        db.close()
