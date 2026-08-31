"""Ordered, redacted runtime event persistence."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assistant.audit import redact_arguments
from app.models import RuntimeEvent
from contracts.runtime import RUNTIME_EVENT_SCHEMA_VERSION, RuntimeEventRecord, RuntimeEventType

from .repository import get_runtime_run_for_update


class RuntimeEventDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: RuntimeEventType
    parent_event_id: str | None = Field(default=None, min_length=1, max_length=36)
    public_summary: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


def append_events(
    db: Session,
    run_id: str,
    events: Sequence[RuntimeEventDraft],
) -> list[RuntimeEvent]:
    """Stage ordered events in the current transaction without committing.

    Locking the parent run serializes concurrent publishers without relying on
    implementation details of LangGraph or a process-local counter.  Callers
    that also update the run can commit both changes atomically.
    """
    if not events:
        return []
    run = get_runtime_run_for_update(db, run_id)
    if run is None:
        raise ValueError("Runtime run not found")

    latest_sequence = db.scalar(
        select(func.max(RuntimeEvent.sequence)).where(RuntimeEvent.run_id == run.id)
    )
    rows = [
        RuntimeEvent(
            run_id=run.id,
            parent_event_id=event.parent_event_id,
            sequence=(latest_sequence or 0) + offset,
            event_type=event.type.value,
            public_summary=event.public_summary,
            payload_json=redact_arguments(event.payload),
            schema_version=RUNTIME_EVENT_SCHEMA_VERSION,
        )
        for offset, event in enumerate(events, start=1)
    ]
    db.add_all(rows)
    db.flush()
    return rows


def publish_event(db: Session, run_id: str, event: RuntimeEventDraft) -> RuntimeEvent:
    """Append and commit one event with a run-local monotonic sequence."""
    row = append_events(db, run_id, [event])[0]
    db.commit()
    db.refresh(row)
    return row


def publish_events(
    db: Session,
    run_id: str,
    events: Sequence[RuntimeEventDraft],
) -> list[RuntimeEvent]:
    """Append and commit a contiguous batch of events."""
    rows = append_events(db, run_id, events)
    if not rows:
        return []
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def list_events_after(db: Session, run_id: str, *, after_sequence: int = 0) -> list[RuntimeEvent]:
    if after_sequence < 0:
        raise ValueError("after_sequence must be non-negative")
    stmt = (
        select(RuntimeEvent)
        .where(RuntimeEvent.run_id == run_id, RuntimeEvent.sequence > after_sequence)
        .order_by(RuntimeEvent.sequence.asc())
    )
    return list(db.scalars(stmt).all())


def latest_event_sequence(db: Session, run_id: str) -> int:
    """Return the last durable sequence for a run without reading its payloads."""
    return db.scalar(select(func.max(RuntimeEvent.sequence)).where(RuntimeEvent.run_id == run_id)) or 0


def to_contract_event(event: RuntimeEvent) -> RuntimeEventRecord:
    return RuntimeEventRecord(
        event_id=event.id,
        run_id=event.run_id,
        parent_event_id=event.parent_event_id,
        sequence=event.sequence,
        type=RuntimeEventType(event.event_type),
        public_summary=event.public_summary,
        payload=event.payload_json or {},
        schema_version=event.schema_version,
        created_at=event.created_at,
    )
