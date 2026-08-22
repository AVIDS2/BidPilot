"""Durable queue handoff for browser-independent assistant execution."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.models import RuntimeRun, TaskOutboxEvent
from app.outbox.service import enqueue_workflow_task, request_task_outbox_dispatch


def enqueue_assistant_run(
    db: Session,
    user: CurrentUser,
    run: RuntimeRun,
) -> TaskOutboxEvent:
    """Persist and publish one idempotent assistant Worker task.

    The database row is the source of truth. A failed broker wake-up is safe:
    Worker Beat will redispatch the pending outbox row later.
    """

    event = enqueue_workflow_task(
        db,
        org_id=user.org_id,
        project_id=run.project_id,
        execution_run_id=run.execution_run_id,
        runtime_run_id=run.id,
        task_name="worker.run_assistant_turn",
        args=[run.id],
        kwargs={},
        deduplication_key=f"assistant-turn:{run.id}",
    )
    db.commit()
    request_task_outbox_dispatch(event.id)
    return event


__all__ = ["enqueue_assistant_run"]
