"""Background long-task tracker for the assistant harness.

Pattern from learn-claude-code s13:
- start slow work in background
- return a placeholder tool result immediately
- on completion, enqueue a wake notification for the conversation
- next assistant turn (or wake endpoint) injects TaskCompleted context

BidPilot maps "slow work" to governed Runtime/workflow child runs rather than
raw shell. The first concrete producer is draft/export workflow completion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import Notification


@dataclass
class BackgroundTask:
    id: str
    conversation_id: str
    user_id: str
    kind: str
    status: str = "running"  # running | succeeded | failed
    title: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None


_LOCK = Lock()
_TASKS: dict[str, BackgroundTask] = {}
_PENDING_WAKES: dict[str, list[str]] = {}  # conversation_id -> [task_id]


def start_background_task(
    *,
    conversation_id: str,
    user_id: str,
    kind: str,
    title: str,
    detail: dict[str, Any] | None = None,
    task_id: str | None = None,
) -> BackgroundTask:
    task = BackgroundTask(
        id=task_id or f"bg_{uuid4().hex[:10]}",
        conversation_id=conversation_id,
        user_id=user_id,
        kind=kind,
        title=title,
        detail=detail or {},
    )
    with _LOCK:
        _TASKS[task.id] = task
    return task


def complete_background_task(
    task_id: str,
    *,
    status: str = "succeeded",
    detail: dict[str, Any] | None = None,
    error: str | None = None,
) -> BackgroundTask | None:
    with _LOCK:
        task = _TASKS.get(task_id)
        if task is None:
            return None
        task.status = status
        task.finished_at = datetime.now(UTC)
        if detail:
            task.detail.update(detail)
        task.error = error
        _PENDING_WAKES.setdefault(task.conversation_id, []).append(task.id)
        return task


def collect_completed_notifications(conversation_id: str) -> list[dict[str, Any]]:
    """Drain completed task notifications for the next agent turn."""
    with _LOCK:
        task_ids = list(_PENDING_WAKES.get(conversation_id) or [])
        _PENDING_WAKES[conversation_id] = []
        notifications: list[dict[str, Any]] = []
        for task_id in task_ids:
            task = _TASKS.get(task_id)
            if task is None:
                continue
            notifications.append(
                {
                    "task_id": task.id,
                    "kind": task.kind,
                    "status": task.status,
                    "title": task.title,
                    "detail": task.detail,
                    "error": task.error,
                }
            )
        return notifications


def bind_workflow_background_task(
    *,
    conversation_id: str,
    user_id: str,
    runtime_run_id: str,
    workflow_run_id: str | None,
    title: str,
) -> BackgroundTask:
    return start_background_task(
        conversation_id=conversation_id,
        user_id=user_id,
        kind="workflow",
        title=title,
        task_id=f"wf_{runtime_run_id[:12]}",
        detail={
            "runtime_run_id": runtime_run_id,
            "workflow_run_id": workflow_run_id,
        },
    )


def mark_workflow_task_finished(
    runtime_run_id: str,
    *,
    status: str,
    summary: str | None = None,
    error: str | None = None,
) -> BackgroundTask | None:
    task_id = f"wf_{runtime_run_id[:12]}"
    return complete_background_task(
        task_id,
        status=status,
        detail={"summary": summary} if summary else None,
        error=error,
    )


def persist_wake_notification(
    db: Session,
    *,
    user_id: str,
    title: str,
    body: str,
    link: str | None = None,
) -> None:
    """Durable user-visible wake signal (bell / inbox)."""
    db.add(
        Notification(
            user_id=user_id,
            type="agent_task",
            title=title[:255],
            body=body,
            link=link,
        )
    )
    db.commit()


__all__ = [
    "BackgroundTask",
    "bind_workflow_background_task",
    "collect_completed_notifications",
    "complete_background_task",
    "mark_workflow_task_finished",
    "persist_wake_notification",
    "start_background_task",
]
