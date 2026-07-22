"""Durable, bounded continuation state for Assistant turns.

The state carries only the pending capability, redacted arguments, and missing
field names. It is deliberately not a transcript, model payload, or hidden
reasoning store.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import ChatTaskState

from .audit import redact_arguments


TASK_STATE_TTL = timedelta(minutes=30)


def get_task_state(db: Session, conversation_id: str) -> ChatTaskState | None:
    return db.get(ChatTaskState, conversation_id)


def set_task_state(
    db: Session,
    conversation_id: str,
    *,
    status: str,
    tool_name: str | None,
    arguments: dict[str, Any],
    missing_fields: list[str] | tuple[str, ...],
) -> ChatTaskState:
    state = get_task_state(db, conversation_id)
    if state is None:
        state = ChatTaskState(conversation_id=conversation_id)
        db.add(state)
    state.status = status
    state.tool_name = tool_name
    state.arguments_json = redact_arguments(arguments)
    state.missing_fields_json = {"fields": list(missing_fields)}
    db.commit()
    db.refresh(state)
    return state


def clear_task_state(db: Session, conversation_id: str) -> None:
    state = get_task_state(db, conversation_id)
    if state is None:
        return
    db.delete(state)
    db.commit()


def is_task_state_stale(task_state: ChatTaskState | None) -> bool:
    if task_state is None or task_state.updated_at is None:
        return False
    return datetime.now(UTC) - task_state.updated_at.replace(tzinfo=UTC) > TASK_STATE_TTL


def pending_input_context(db: Session, conversation_id: str) -> dict[str, Any] | None:
    """Return a safe planning context for an unexpired missing-input turn."""
    state = get_task_state(db, conversation_id)
    if state is None or state.status != "needs_input" or not state.tool_name:
        return None
    if is_task_state_stale(state):
        clear_task_state(db, conversation_id)
        return None

    raw_fields = (state.missing_fields_json or {}).get("fields") or []
    missing_fields = [field for field in raw_fields if isinstance(field, str) and field]
    if not missing_fields:
        return None
    return {
        "capability_name": state.tool_name,
        "arguments": redact_arguments(state.arguments_json or {}),
        "missing_fields": missing_fields,
    }


__all__ = [
    "TASK_STATE_TTL",
    "clear_task_state",
    "get_task_state",
    "is_task_state_stale",
    "pending_input_context",
    "set_task_state",
]
