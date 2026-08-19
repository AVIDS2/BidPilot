"""Durable control plane for Pi's first-party subagent extension.

The Pi extension only describes delegation.  This module owns tenant scope,
depth/width budgets, durable child runs and Worker delivery.  It intentionally
does not execute a child in-process, so a model cannot escape the API policy
boundary by asking Pi to spawn a local process.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.chat.service import _fallback_conversation_title
from app.models import ChatConversation, RuntimeRun, TaskOutboxEvent
from app.outbox.service import enqueue_workflow_task, request_task_outbox_dispatch
from contracts.runtime import RuntimeEventType, RuntimeRunKind, RuntimeRunStatus

from .events import RuntimeEventDraft, append_events
from .pi_config import pi_execution_contract
from .repository import get_visible_runtime_run
from .service import create_runtime_run, find_idempotent_runtime_run

MAX_CHILDREN_PER_RUN = 8
MAX_ALLOWED_DEPTH = 3
DEFAULT_MAX_STEPS = 8
MAX_STEPS = 32
MAX_TASK_CHARACTERS = 12_000
MAX_FOREGROUND_WAIT_SECONDS = 55
DEFAULT_FOREGROUND_WAIT_SECONDS = 45
SUBAGENT_POLL_INTERVAL_SECONDS = 0.5
TERMINAL_SUBAGENT_STATUSES = frozenset({
    RuntimeRunStatus.SUCCEEDED.value,
    RuntimeRunStatus.FAILED.value,
    RuntimeRunStatus.CANCELLED.value,
    RuntimeRunStatus.EXPIRED.value,
})


@dataclass(frozen=True)
class SubagentTask:
    task: str
    agent: str = "general"
    task_id: str | None = None


def _depth(db: Session, run: RuntimeRun) -> int:
    depth = 0
    current = run
    seen: set[str] = set()
    while current.parent_run_id and current.parent_run_id not in seen:
        seen.add(current.id)
        parent = db.get(RuntimeRun, current.parent_run_id)
        if parent is None:
            break
        depth += 1
        current = parent
    return depth


def _normalize_tasks(arguments: dict[str, Any]) -> tuple[Literal["single", "parallel", "chain"], list[SubagentTask]]:
    mode = arguments.get("mode")
    if mode not in {"single", "parallel", "chain"}:
        raise ValueError("subagent_mode_invalid")
    if mode == "single":
        task = str(arguments.get("task") or "").strip()
        if not task:
            raise ValueError("subagent_task_required")
        raw_tasks = [{"task": task, "agent": arguments.get("agent")}]
    else:
        key = "tasks" if mode == "parallel" else "chain"
        raw_tasks = arguments.get(key)
        if not isinstance(raw_tasks, list) or not raw_tasks:
            raise ValueError("subagent_tasks_required")
    if len(raw_tasks) > MAX_CHILDREN_PER_RUN:
        raise ValueError("subagent_children_limit")
    normalized: list[SubagentTask] = []
    for index, item in enumerate(raw_tasks):
        if not isinstance(item, dict):
            raise ValueError("subagent_task_invalid")
        task = str(item.get("task") or "").strip()
        if not task or len(task) > MAX_TASK_CHARACTERS:
            raise ValueError("subagent_task_invalid")
        agent = str(item.get("agent") or "general").strip()[:80] or "general"
        task_id = str(item.get("task_id") or f"task-{index + 1}").strip()[:80]
        normalized.append(SubagentTask(task=task, agent=agent, task_id=task_id))
    return mode, normalized


def create_subagent_runs(
    db: Session,
    user: CurrentUser,
    *,
    parent_run_id: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Create and enqueue bounded children, returning a model-safe observation."""
    parent = get_visible_runtime_run(db, parent_run_id, user)
    if parent is None:
        raise ValueError("subagent_parent_not_found")
    if parent.status not in {RuntimeRunStatus.RUNNING.value, RuntimeRunStatus.AWAITING_APPROVAL.value}:
        raise ValueError("subagent_parent_not_executable")
    if _depth(db, parent) >= MAX_ALLOWED_DEPTH:
        raise ValueError("subagent_depth_limit")
    mode, tasks = _normalize_tasks(arguments)
    max_steps = int(arguments.get("max_steps") or DEFAULT_MAX_STEPS)
    if max_steps < 1 or max_steps > MAX_STEPS:
        raise ValueError("subagent_steps_limit")

    append_events(db, parent.id, [RuntimeEventDraft(
        type=RuntimeEventType.CAPABILITY_STARTED,
        public_summary=f"正在派生 {len(tasks)} 个受治理子 Agent。",
        payload={"capability": "spawn_subagents", "mode": mode, "count": len(tasks)},
    )])

    children: list[dict[str, Any]] = []
    pending_dispatch_ids: list[str] = []
    previous_child_id: str | None = None
    execution_contract = pi_execution_contract()
    for index, task in enumerate(tasks):
        idempotency_key = f"subagent:{parent.id}:{task.task_id}"
        existing = find_idempotent_runtime_run(db, user, idempotency_key=idempotency_key)
        if existing is not None:
            outbox = db.scalar(
                select(TaskOutboxEvent)
                .where(TaskOutboxEvent.runtime_run_id == existing.id)
                .order_by(TaskOutboxEvent.created_at.desc())
                .limit(1)
            )
            children.append({
                "run_id": existing.id,
                "trace_id": existing.trace_id,
                "task_id": task.task_id,
                "profile": task.agent,
                "status": existing.status,
                "mode": mode,
                "outbox_event_id": outbox.id if outbox is not None else None,
            })
            previous_child_id = existing.id
            continue
        conversation = ChatConversation(
            user_id=user.id,
            project_id=parent.project_id,
            source_conversation_id=parent.conversation_id,
            title=_fallback_conversation_title(f"{task.agent}: {task.task}"),
        )
        db.add(conversation)
        db.flush()
        child = create_runtime_run(
            db,
            user,
            kind=RuntimeRunKind.SUBAGENT.value,
            engine="pi_subagent_worker",
            project_id=parent.project_id,
            conversation_id=conversation.id,
            parent_run_id=parent.id,
            provider_config_id=parent.provider_config_id,
            model=parent.model,
            reasoning_effort=parent.reasoning_effort,
            approval_mode="risky_only",
            idempotency_key=idempotency_key,
            input_json={
                "subagent": {
                    "mode": mode,
                    "profile": task.agent,
                    "prompt": task.task,
                    "task_id": task.task_id,
                    "task_index": index,
                    "previous_child_run_id": previous_child_id,
                    "max_steps": max_steps,
                    "pi_runtime": execution_contract,
                },
            },
            commit=False,
        )
        child.status = RuntimeRunStatus.QUEUED.value
        outbox = enqueue_workflow_task(
            db,
            org_id=user.org_id,
            project_id=parent.project_id,
            execution_run_id=None,
            runtime_run_id=child.id,
            task_name="worker.run_subagent",
            args=[child.id],
            kwargs={},
            deduplication_key=f"subagent:{child.id}",
        )
        children.append({
            "run_id": child.id,
            "trace_id": child.trace_id,
            "task_id": task.task_id,
            "profile": task.agent,
            "status": child.status,
            "mode": mode,
            "outbox_event_id": outbox.id,
        })
        pending_dispatch_ids.append(outbox.id)
        previous_child_id = child.id

    append_events(db, parent.id, [RuntimeEventDraft(
        type=RuntimeEventType.CAPABILITY_SUCCEEDED,
        public_summary=f"已派生 {len(children)} 个子 Agent，已进入后台队列。",
        payload={"capability": "spawn_subagents", "mode": mode, "children": children},
    )])
    db.commit()
    for event_id in pending_dispatch_ids:
        request_task_outbox_dispatch(event_id)
    return {
        "mode": mode,
        "children": children,
        "status": "queued",
        "resumable": True,
        "next_step": "wait_for_subagent_updates",
    }


def wait_for_subagent_results(
    db: Session,
    user: CurrentUser,
    *,
    parent_run_id: str,
    child_run_ids: list[str],
    timeout_seconds: int = DEFAULT_FOREGROUND_WAIT_SECONDS,
) -> dict[str, Any]:
    """Wait briefly for durable children and return a model-safe observation.

    The children remain Worker-owned durable runs. This wait only joins their
    terminal observations back into the current Pi turn; it never executes a
    child inside the API process.
    """
    unique_ids = list(dict.fromkeys(str(value).strip() for value in child_run_ids if str(value).strip()))
    if not unique_ids or len(unique_ids) > MAX_CHILDREN_PER_RUN:
        raise ValueError("subagent_children_invalid")
    bounded_timeout = min(max(int(timeout_seconds), 1), MAX_FOREGROUND_WAIT_SECONDS)
    deadline = time.monotonic() + bounded_timeout
    ordered_rows: list[RuntimeRun] = []

    while True:
        db.expire_all()
        rows = list(db.scalars(
            select(RuntimeRun).where(
                RuntimeRun.id.in_(unique_ids),
                RuntimeRun.parent_run_id == parent_run_id,
                RuntimeRun.user_id == user.id,
                RuntimeRun.org_id == user.org_id,
                RuntimeRun.kind == RuntimeRunKind.SUBAGENT.value,
            )
        ))
        by_id = {row.id: row for row in rows}
        if len(by_id) != len(unique_ids):
            raise ValueError("subagent_child_scope_mismatch")
        ordered_rows = [by_id[child_id] for child_id in unique_ids]
        if all(row.status in TERMINAL_SUBAGENT_STATUSES for row in ordered_rows):
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(SUBAGENT_POLL_INTERVAL_SECONDS)

    children: list[dict[str, Any]] = []
    for row in ordered_rows:
        contract = (row.input_json or {}).get("subagent") or {}
        result = row.result_json if isinstance(row.result_json, dict) else {}
        summary = result.get("summary") if isinstance(result.get("summary"), str) else None
        if not summary and row.status == RuntimeRunStatus.FAILED.value:
            summary = row.error_message or "子 Agent 执行失败。"
        children.append({
            "run_id": row.id,
            "task_id": contract.get("task_id"),
            "profile": contract.get("profile"),
            "status": row.status,
            "summary": summary,
            "error_code": row.error_code,
        })

    completed = all(child["status"] in TERMINAL_SUBAGENT_STATUSES for child in children)
    return {
        "status": "completed" if completed else "waiting",
        "completed": completed,
        "children": children,
        "resumable": not completed,
        "next_step": "synthesize_child_results" if completed else "continue_after_background_notification",
    }


__all__ = ["create_subagent_runs", "wait_for_subagent_results"]
