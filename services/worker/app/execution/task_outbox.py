"""Worker-side dispatch and consumer leases for durable workflow task intents."""

from __future__ import annotations

import logging
from datetime import timedelta

from app.db import SessionLocal
from contracts.task_outbox import (
    claim_task_outbox_delivery,
    claim_task_outbox_dispatch,
    complete_task_outbox_delivery,
    fail_task_outbox_delivery,
    list_dispatchable_task_outbox_event_ids,
    mark_task_outbox_dispatched,
    return_task_outbox_to_pending,
)


logger = logging.getLogger(__name__)

_ALLOWED_TASKS = {
    "worker.draft_section",
    "worker.extract_memory_graph",
    "worker.resume_draft",
    "worker.run_subagent",
    "worker.run_deep_research",
    "worker.run_assistant_turn",
}
_PUBLISH_RETRY_DELAY = timedelta(minutes=1)


def _send_task(task_name: str, *, args: list, kwargs: dict, task_id: str) -> None:
    """Load Celery only at publish time to avoid task-autodiscovery cycles."""
    from app.celery_app import celery_app

    celery_app.send_task(task_name, args=args, kwargs=kwargs, task_id=task_id)


def dispatch_task_outbox_event(event_id: str) -> dict[str, str]:
    """Publish one claimed task intent after its database transaction committed."""
    db = SessionLocal()
    try:
        event = claim_task_outbox_dispatch(db, event_id=event_id)
        if event is None:
            db.commit()
            return {"status": "not_due", "event_id": event_id}
        task_name = event.task_name
        args = list(event.args_json)
        kwargs = dict(event.kwargs_json)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Task outbox dispatch claim failed: event=%s", event_id)
        raise
    finally:
        db.close()

    if task_name not in _ALLOWED_TASKS:
        _mark_task_outbox_failed(event_id, "unsupported_task")
        return {"status": "failed", "event_id": event_id}

    try:
        kwargs["outbox_event_id"] = event_id
        _send_task(
            task_name,
            args=args,
            kwargs=kwargs,
            task_id=f"outbox:{event_id}",
        )
    except Exception as exc:
        _return_task_outbox_to_pending(event_id, "task_publish_failed")
        logger.warning(
            "Task outbox publish failed: event=%s error_type=%s",
            event_id,
            type(exc).__name__,
        )
        return {"status": "pending", "event_id": event_id}

    db = SessionLocal()
    try:
        mark_task_outbox_dispatched(db, event_id=event_id)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Task outbox dispatch acknowledgement failed: event=%s", event_id)
        raise
    finally:
        db.close()
    return {"status": "dispatched", "event_id": event_id}


def recover_pending_task_outbox_events(*, batch_size: int = 100) -> dict[str, str]:
    """Recover pending or expired workflow task delivery leases from Worker Beat."""
    db = SessionLocal()
    try:
        event_ids = list_dispatchable_task_outbox_event_ids(db, limit=batch_size)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Task outbox recovery query failed")
        raise
    finally:
        db.close()

    dispatched = 0
    pending = 0
    failed = 0
    for event_id in event_ids:
        result = dispatch_task_outbox_event(event_id)
        if result["status"] == "dispatched":
            dispatched += 1
        elif result["status"] == "pending":
            pending += 1
        elif result["status"] == "failed":
            failed += 1
    return {
        "status": "ok",
        "scanned": str(len(event_ids)),
        "dispatched": str(dispatched),
        "pending": str(pending),
        "failed": str(failed),
    }


def claim_workflow_task_delivery(event_id: str | None) -> bool:
    """Return false for a duplicate broker delivery with an active lease."""
    if not event_id:
        return True
    db = SessionLocal()
    try:
        claimed = claim_task_outbox_delivery(db, event_id=event_id)
        db.commit()
        return claimed
    except Exception:
        db.rollback()
        logger.exception("Task outbox consumer claim failed: event=%s", event_id)
        raise
    finally:
        db.close()


def complete_workflow_task_delivery(event_id: str | None) -> None:
    if not event_id:
        return
    db = SessionLocal()
    try:
        complete_task_outbox_delivery(db, event_id=event_id)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Task outbox completion write failed: event=%s", event_id)
        raise
    finally:
        db.close()


def fail_workflow_task_delivery(event_id: str | None, error_code: str) -> None:
    if not event_id:
        return
    db = SessionLocal()
    try:
        fail_task_outbox_delivery(db, event_id=event_id, error_code=error_code)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Task outbox failure write failed: event=%s", event_id)
        raise
    finally:
        db.close()


def retry_workflow_task_delivery(
    event_id: str | None,
    error_code: str,
    *,
    delay_seconds: int = 30,
) -> None:
    """Release a claimed task before Celery schedules a transient retry."""

    if not event_id:
        return
    db = SessionLocal()
    try:
        return_task_outbox_to_pending(
            db,
            event_id=event_id,
            error_code=error_code,
            retry_after=timedelta(seconds=max(1, delay_seconds)),
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Task outbox retry release failed: event=%s", event_id)
        raise
    finally:
        db.close()


def _return_task_outbox_to_pending(event_id: str, error_code: str) -> None:
    db = SessionLocal()
    try:
        return_task_outbox_to_pending(
            db,
            event_id=event_id,
            error_code=error_code,
            retry_after=_PUBLISH_RETRY_DELAY,
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Task outbox retry state write failed: event=%s", event_id)
        raise
    finally:
        db.close()


def _mark_task_outbox_failed(event_id: str, error_code: str) -> None:
    db = SessionLocal()
    try:
        fail_task_outbox_delivery(db, event_id=event_id, error_code=error_code)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Task outbox terminal state write failed: event=%s", event_id)
        raise
    finally:
        db.close()
