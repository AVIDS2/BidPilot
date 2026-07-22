"""SSE streaming for drafting runs backed by product runtime events.

LangGraph checkpoints recover graph execution; they are deliberately not a
product event API.  New drafting runs expose progress through ``RuntimeEvent``
records, while older unbridged runs fall back to coarse ``ExecutionRun`` status
polling only.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExecutionRun, RuntimeEvent, RuntimeRun
from app.runtime.events import list_events_after

_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled", "error", "expired"})
_POLL_INTERVAL = 1.5
_MAX_STREAM_SECONDS = 300


def _sse_event(event: str, data: dict[str, Any]) -> dict[str, str]:
    return {"event": event, "data": json.dumps(data, default=str)}


async def stream_graph_events(run_id: str, db: Session):
    """Yield compatible drafting SSE events from the durable runtime timeline."""
    execution_run = db.get(ExecutionRun, run_id)
    if execution_run is None:
        yield _sse_event("graph_error", {"error_message": "运行记录不存在。"})
        return

    runtime_run = _find_workflow_runtime_run(db, run_id)
    yield _sse_event(
        "connected",
        {
            "run_id": run_id,
            "runtime_run_id": runtime_run.id if runtime_run is not None else None,
            "status": execution_run.status,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )

    if runtime_run is None:
        async for event in _stream_legacy_status(run_id, db):
            yield event
        return

    after_sequence = 0
    elapsed = 0.0
    while elapsed < _MAX_STREAM_SECONDS:
        db.expire_all()
        runtime_run = db.get(RuntimeRun, runtime_run.id)
        execution_run = db.get(ExecutionRun, run_id)
        if runtime_run is None or execution_run is None:
            yield _sse_event("graph_error", {"error_message": "运行记录不可用。"})
            return

        events = list_events_after(db, runtime_run.id, after_sequence=after_sequence)
        for event in events:
            after_sequence = event.sequence
            for mapped in _map_runtime_event(event, runtime_run):
                yield mapped

        if runtime_run.status in _TERMINAL_STATUSES:
            return

        await asyncio.sleep(_POLL_INTERVAL)
        elapsed += _POLL_INTERVAL

    yield _sse_event("graph_error", {"error_message": f"工作流状态等待超时（{_MAX_STREAM_SECONDS} 秒）。"})


def _find_workflow_runtime_run(db: Session, execution_run_id: str) -> RuntimeRun | None:
    return db.scalar(
        select(RuntimeRun)
        .where(RuntimeRun.execution_run_id == execution_run_id)
        .order_by(RuntimeRun.created_at.desc())
        .limit(1)
    )


def _map_runtime_event(event: RuntimeEvent, runtime_run: RuntimeRun) -> list[dict[str, str]]:
    payload = event.payload_json or {}
    node_name = str(payload.get("node") or payload.get("capability") or "workflow")
    timestamp = event.created_at.isoformat() if event.created_at else datetime.now(UTC).isoformat()
    if event.event_type == "capability.started":
        return [_sse_event("node_started", {"node_name": node_name, "timestamp": timestamp})]
    if event.event_type == "capability.succeeded":
        mapped = [
            _sse_event(
                "node_completed",
                {"node_name": node_name, "result_summary": event.public_summary, "timestamp": timestamp},
            )
        ]
        if node_name == "quality_reviewer":
            mapped.append(
                _sse_event(
                    "review_result",
                    {
                        "passed": bool(payload.get("passed")),
                        "issues": [],
                        "score": payload.get("score") or 0,
                    },
                )
            )
        return mapped
    if event.event_type == "capability.failed":
        return [
            _sse_event(
                "graph_error",
                {
                    "error_message": event.public_summary,
                    "error_code": payload.get("error_code"),
                    "node_name": node_name,
                    "timestamp": timestamp,
                },
            )
        ]
    if event.event_type == "capability.progressed" and payload.get("phase") == "provider_retry":
        return [
            _sse_event(
                "provider_retry",
                {
                    "node_name": node_name,
                    "error_code": payload.get("error_code"),
                    "attempt": payload.get("next_attempt"),
                    "max_attempts": payload.get("max_attempts"),
                    "timestamp": timestamp,
                },
            )
        ]
    if event.event_type == "capability.progressed" and payload.get("phase") == "cancellation_requested":
        return [_sse_event("graph_cancellation_requested", {"timestamp": timestamp})]
    if event.event_type == "approval.requested":
        return [
            _sse_event(
                "human_approval_required",
                {
                    "draft_preview": "",
                    "review_score": payload.get("review_score"),
                    "timestamp": timestamp,
                },
            )
        ]
    if event.event_type == "approval.resolved":
        return [
            _sse_event(
                "node_completed",
                {"node_name": "human_approval", "result_summary": event.public_summary, "timestamp": timestamp},
            )
        ]
    if event.event_type == "run.completed":
        result = runtime_run.result_json or {}
        return [
            _sse_event(
                "graph_completed",
                {
                    "persisted": True,
                    "section_version_id": result.get("section_version_id"),
                    "status": "succeeded",
                    "timestamp": timestamp,
                },
            )
        ]
    if event.event_type == "run.cancelled":
        return [_sse_event("graph_cancelled", {"status": "cancelled", "timestamp": timestamp})]
    if event.event_type == "run.failed":
        status = str(payload.get("status") or runtime_run.status)
        return [
            _sse_event(
                "graph_error",
                {
                    "error_message": event.public_summary,
                    "error_code": payload.get("error_code"),
                    "status": status,
                    "timestamp": timestamp,
                },
            )
        ]
    return []


async def _stream_legacy_status(run_id: str, db: Session):
    """Compatibility status-only fallback for runs created before bridge rollout."""
    elapsed = 0.0
    while elapsed < _MAX_STREAM_SECONDS:
        db.expire_all()
        run = db.get(ExecutionRun, run_id)
        if run is None:
            yield _sse_event("graph_error", {"error_message": "运行记录不可用。"})
            return
        if run.status in _TERMINAL_STATUSES:
            output = run.output_json or {}
            if run.status == "succeeded":
                yield _sse_event(
                    "graph_completed",
                    {
                        "persisted": True,
                        "section_version_id": output.get("section_version_id"),
                        "status": run.status,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )
            else:
                yield _sse_event(
                    "graph_error",
                    {"error_message": str(output.get("error") or "工作流未能完成。")},
                )
            return
        yield _sse_event(
            "heartbeat",
            {
                "run_id": run_id,
                "status": run.status,
                "elapsed_seconds": round(elapsed, 1),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        await asyncio.sleep(_POLL_INTERVAL)
        elapsed += _POLL_INTERVAL

    yield _sse_event("graph_error", {"error_message": f"工作流状态等待超时（{_MAX_STREAM_SECONDS} 秒）。"})
