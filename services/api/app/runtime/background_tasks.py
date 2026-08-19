"""Durable background-work notifications for the assistant harness.

Long-running workflow state belongs to ``RuntimeRun`` / ``RuntimeEvent`` and
the user-facing wake signal belongs to ``Notification``.  This module only
projects those persisted records into the next assistant turn; it deliberately
keeps no process-local task registry, so an API restart cannot lose a wake.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Notification, RuntimeEvent, RuntimeRun


_TERMINAL_WORKFLOW_STATUSES = frozenset({"succeeded", "failed", "cancelled", "expired"})


def collect_completed_notifications(
    db: Session,
    *,
    conversation_id: str,
    user_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Consume durable workflow wakes for one conversation.

    Worker terminal transitions commit the ``agent_task`` notification in the
    same transaction as the terminal runtime event.  Marking a matching wake
    read after it is added to the model context gives the next turn exactly-once
    delivery semantics without a second in-memory queue.
    """
    notifications = list(
        db.scalars(
            select(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.type == "agent_task",
                Notification.read.is_(False),
            )
            .order_by(Notification.created_at.asc(), Notification.id.asc())
            .limit(max(1, min(limit, 50)))
        )
    )
    updates: list[dict[str, Any]] = []
    for notification in notifications:
        runtime_run_id = _runtime_run_id_from_wake_link(notification.link, conversation_id)
        if runtime_run_id is None:
            continue
        runtime_run = db.scalar(
            select(RuntimeRun).where(
                RuntimeRun.id == runtime_run_id,
                RuntimeRun.user_id == user_id,
                RuntimeRun.kind.in_(("workflow_bridge", "subagent")),
            )
        )
        if runtime_run is None or runtime_run.status not in _TERMINAL_WORKFLOW_STATUSES:
            continue
        if runtime_run.kind == "workflow_bridge":
            belongs_to_conversation = runtime_run.conversation_id == conversation_id
        else:
            parent = db.get(RuntimeRun, runtime_run.parent_run_id) if runtime_run.parent_run_id else None
            belongs_to_conversation = parent is not None and parent.conversation_id == conversation_id
        if not belongs_to_conversation:
            continue
        terminal_event = db.scalar(
            select(RuntimeEvent)
            .where(RuntimeEvent.run_id == runtime_run.id)
            .order_by(RuntimeEvent.sequence.desc())
            .limit(1)
        )
        updates.append(
            {
                "task_id": notification.id,
                "kind": "subagent" if runtime_run.kind == "subagent" else "workflow",
                "status": runtime_run.status,
                "title": notification.title,
                "detail": {
                    "runtime_run_id": runtime_run.id,
                    "workflow_run_id": runtime_run.execution_run_id,
                    "project_id": runtime_run.project_id,
                    "summary": (
                        str((runtime_run.result_json or {}).get("summary") or "").strip()
                        if runtime_run.kind == "subagent"
                        else ""
                    ) or (
                        terminal_event.public_summary
                        if terminal_event is not None
                        else notification.body or "后台工作流已更新。"
                    ),
                },
            }
        )
        notification.read = True
    if updates:
        db.commit()
    return updates


def _runtime_run_id_from_wake_link(link: str | None, conversation_id: str) -> str | None:
    if not link:
        return None
    parsed = urlparse(link)
    if not parsed.path.startswith("/agent"):
        return None
    query = parse_qs(parsed.query)
    if query.get("conversation", [None])[0] != conversation_id:
        return None
    runtime_run_id = query.get("wake", [None])[0]
    return runtime_run_id if isinstance(runtime_run_id, str) and runtime_run_id else None


__all__ = ["collect_completed_notifications"]
