"""Write workflow task intents transactionally and request post-commit delivery."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.celery_client import celery
from app.models import TaskOutboxEvent
from contracts.task_outbox import create_task_outbox_event


logger = logging.getLogger(__name__)


def enqueue_workflow_task(
    db: Session,
    *,
    org_id: str,
    project_id: str | None,
    execution_run_id: str | None,
    runtime_run_id: str | None,
    task_name: str,
    args: list,
    kwargs: dict,
    deduplication_key: str,
) -> TaskOutboxEvent:
    """Persist one allow-listed workflow task intent in the current API transaction."""
    return create_task_outbox_event(
        db,
        org_id=org_id,
        project_id=project_id,
        execution_run_id=execution_run_id,
        runtime_run_id=runtime_run_id,
        task_name=task_name,
        args=args,
        kwargs=kwargs,
        deduplication_key=deduplication_key,
    )


def request_task_outbox_dispatch(event_id: str) -> bool:
    """Wake a Worker after commit; Beat recovery handles a failed wake-up."""
    try:
        celery.send_task("worker.dispatch_task_outbox_event", args=[event_id])
        return True
    except Exception:
        logger.warning("Task outbox wake-up publish failed: event=%s", event_id)
        return False
