"""Shared transactional-outbox state transitions for internal task delivery."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import TaskOutboxEvent


OUTBOX_DISPATCH_LEASE = timedelta(minutes=5)
OUTBOX_DELIVERY_LEASE = timedelta(minutes=20)


def _now(now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    if current.tzinfo is not None:
        return current.replace(tzinfo=None)
    return current


def create_task_outbox_event(
    db: Session,
    *,
    org_id: str,
    task_name: str,
    args: list,
    kwargs: dict,
    deduplication_key: str,
    project_id: str | None = None,
    execution_run_id: str | None = None,
    runtime_run_id: str | None = None,
    now: datetime | None = None,
) -> TaskOutboxEvent:
    """Write or return one idempotent internal task record in the caller's transaction."""
    existing = db.scalar(
        select(TaskOutboxEvent)
        .where(
            TaskOutboxEvent.org_id == org_id,
            TaskOutboxEvent.deduplication_key == deduplication_key,
        )
        .with_for_update()
    )
    if existing is not None:
        return existing
    event = TaskOutboxEvent(
        org_id=org_id,
        project_id=project_id,
        execution_run_id=execution_run_id,
        runtime_run_id=runtime_run_id,
        task_name=task_name,
        args_json=list(args),
        kwargs_json=dict(kwargs),
        deduplication_key=deduplication_key,
        status="pending",
        available_at=_now(now),
    )
    try:
        # The pre-read handles the ordinary path. A savepoint converts the
        # remaining concurrent unique-key race into the same idempotent result
        # without rolling back the caller's workflow transaction.
        with db.begin_nested():
            db.add(event)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(TaskOutboxEvent)
            .where(
                TaskOutboxEvent.org_id == org_id,
                TaskOutboxEvent.deduplication_key == deduplication_key,
            )
            .with_for_update()
        )
        if existing is None:
            raise
        return existing
    return event


def claim_task_outbox_dispatch(
    db: Session,
    *,
    event_id: str,
    now: datetime | None = None,
) -> TaskOutboxEvent | None:
    """Claim one due event for broker publication without holding a network lock."""
    current = _now(now)
    event = db.scalar(
        select(TaskOutboxEvent).where(TaskOutboxEvent.id == event_id).with_for_update()
    )
    if event is None or event.status in {"completed", "failed", "cancelled"}:
        return None
    if event.status == "pending":
        if event.available_at > current:
            return None
    elif event.status in {"dispatching", "dispatched", "processing"}:
        if event.lease_expires_at is not None and event.lease_expires_at > current:
            return None
    else:
        return None
    event.status = "dispatching"
    event.dispatch_attempts += 1
    event.lease_expires_at = current + OUTBOX_DISPATCH_LEASE
    event.last_error_code = None
    db.flush()
    return event


def mark_task_outbox_dispatched(
    db: Session,
    *,
    event_id: str,
    now: datetime | None = None,
) -> None:
    """Record broker acceptance unless the consumer has already claimed it."""
    event = db.scalar(
        select(TaskOutboxEvent).where(TaskOutboxEvent.id == event_id).with_for_update()
    )
    if event is None:
        return
    if event.status == "dispatching":
        event.status = "dispatched"
        event.dispatched_at = _now(now)
        db.flush()


def return_task_outbox_to_pending(
    db: Session,
    *,
    event_id: str,
    error_code: str,
    retry_after: timedelta,
    now: datetime | None = None,
) -> None:
    """Make a broker-publication failure recoverable without raw exception text."""
    event = db.scalar(
        select(TaskOutboxEvent).where(TaskOutboxEvent.id == event_id).with_for_update()
    )
    if event is None or event.status == "completed":
        return
    current = _now(now)
    event.status = "pending"
    event.available_at = current + retry_after
    event.lease_expires_at = None
    event.last_error_code = error_code
    db.flush()


def claim_task_outbox_delivery(
    db: Session,
    *,
    event_id: str,
    now: datetime | None = None,
) -> bool:
    """Claim one broker delivery so duplicate task messages exit safely."""
    current = _now(now)
    event = db.scalar(
        select(TaskOutboxEvent).where(TaskOutboxEvent.id == event_id).with_for_update()
    )
    if event is None or event.status in {"completed", "failed", "cancelled", "pending"}:
        return False
    if event.status == "processing" and event.lease_expires_at is not None:
        if event.lease_expires_at > current:
            return False
    elif event.status not in {"dispatching", "dispatched", "processing"}:
        return False
    event.status = "processing"
    event.delivery_attempts += 1
    event.lease_expires_at = current + OUTBOX_DELIVERY_LEASE
    db.flush()
    return True


def complete_task_outbox_delivery(
    db: Session,
    *,
    event_id: str,
    now: datetime | None = None,
) -> None:
    """Mark an internal workflow task completed after its terminal handler exits."""
    event = db.scalar(
        select(TaskOutboxEvent).where(TaskOutboxEvent.id == event_id).with_for_update()
    )
    if event is None or event.status == "completed":
        return
    event.status = "completed"
    event.completed_at = _now(now)
    event.lease_expires_at = None
    event.last_error_code = None
    db.flush()


def fail_task_outbox_delivery(
    db: Session,
    *,
    event_id: str,
    error_code: str,
) -> None:
    """Preserve a terminal task failure as a safe operational state."""
    event = db.scalar(
        select(TaskOutboxEvent).where(TaskOutboxEvent.id == event_id).with_for_update()
    )
    if event is None or event.status == "completed":
        return
    event.status = "failed"
    event.lease_expires_at = None
    event.last_error_code = error_code
    db.flush()


def list_dispatchable_task_outbox_event_ids(
    db: Session,
    *,
    limit: int,
    now: datetime | None = None,
) -> list[str]:
    """Return due events; callers claim each row again before broker I/O."""
    current = _now(now)
    return list(
        db.scalars(
            select(TaskOutboxEvent.id)
            .where(
                or_(
                    and_(
                        TaskOutboxEvent.status == "pending",
                        TaskOutboxEvent.available_at <= current,
                    ),
                    and_(
                        TaskOutboxEvent.status.in_(("dispatching", "dispatched", "processing")),
                        TaskOutboxEvent.lease_expires_at.is_not(None),
                        TaskOutboxEvent.lease_expires_at <= current,
                    ),
                )
            )
            .order_by(TaskOutboxEvent.available_at.asc(), TaskOutboxEvent.created_at.asc())
            .limit(limit)
        )
    )
