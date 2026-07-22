"""Worker-safe publisher for product-owned runtime events.

The worker writes public progress to the same PostgreSQL runtime log as the
API.  It intentionally does not import API services or inspect LangGraph
checkpoint tables; checkpoints remain execution-recovery internals only.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import logging
import re
from typing import Any

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import RuntimeEvent, RuntimeRun
from contracts.runtime import RuntimeEventType

logger = logging.getLogger(__name__)

_SENSITIVE_KEY_MARKERS = ("api_key", "apikey", "token", "secret", "password", "authorization")
_SECRET_TEXT_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*[^\s,;]+"),
)


class RuntimeCancellationRequested(Exception):
    """Raised by the worker at a safe graph-node boundary after cancellation."""


def publish_runtime_event(
    runtime_run_id: str | None,
    event_type: RuntimeEventType,
    public_summary: str,
    payload: dict[str, Any] | None = None,
    *,
    once_key: str | None = None,
) -> RuntimeEvent | None:
    """Append one redacted event with a run-local monotonic sequence.

    A missing runtime id means the job predates bridge rollout; callers may
    continue legacy work, but a present bridge must fail loudly if its event
    cannot be persisted.
    """
    if not runtime_run_id:
        return None
    db = SessionLocal()
    try:
        run = db.scalar(select(RuntimeRun).where(RuntimeRun.id == runtime_run_id).with_for_update())
        if run is None:
            raise ValueError(f"Runtime run {runtime_run_id} not found")
        safe_payload = redact_payload(payload or {})
        if once_key:
            if _has_once_key(db, run.id, event_type.value, once_key):
                return None
            safe_payload["event_key"] = once_key
        latest = db.scalar(select(func.max(RuntimeEvent.sequence)).where(RuntimeEvent.run_id == run.id)) or 0
        event = RuntimeEvent(
            run_id=run.id,
            sequence=latest + 1,
            event_type=event_type.value,
            public_summary=redact_text(public_summary),
            payload_json=safe_payload,
            schema_version="1.0",
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
    except Exception:
        db.rollback()
        logger.exception("Failed to publish runtime event", extra={"runtime_run_id": runtime_run_id})
        raise
    finally:
        db.close()


def publish_node_started(runtime_run_id: str | None, node_name: str) -> RuntimeEvent | None:
    return publish_runtime_event(
        runtime_run_id,
        RuntimeEventType.CAPABILITY_STARTED,
        f"正在执行{_node_label(node_name)}。",
        {"capability": node_name, "node": node_name},
    )


def publish_node_succeeded(
    runtime_run_id: str | None,
    node_name: str,
    summary: str,
    payload: dict[str, Any] | None = None,
) -> RuntimeEvent | None:
    return publish_runtime_event(
        runtime_run_id,
        RuntimeEventType.CAPABILITY_SUCCEEDED,
        summary,
        {"capability": node_name, "node": node_name, **(payload or {})},
    )


def publish_node_failed(
    runtime_run_id: str | None,
    node_name: str,
    _message: str,
    *,
    error_code: str | None = None,
) -> RuntimeEvent | None:
    """Record a node failure without exposing exception text in public events."""
    payload: dict[str, Any] = {"capability": node_name, "node": node_name}
    if error_code:
        payload["error_code"] = error_code
    return publish_runtime_event(
        runtime_run_id,
        RuntimeEventType.CAPABILITY_FAILED,
        "工作流步骤未能完成。",
        payload,
    )


def publish_provider_retry(
    runtime_run_id: str | None,
    *,
    node_name: str,
    error_code: str,
    next_attempt: int,
    max_attempts: int,
) -> RuntimeEvent | None:
    """Record a retry without exposing provider diagnostics or credentials."""
    return publish_runtime_event(
        runtime_run_id,
        RuntimeEventType.CAPABILITY_PROGRESSED,
        "模型服务暂时不可用，正在重试。",
        {
            "capability": node_name,
            "node": node_name,
            "phase": "provider_retry",
            "error_code": error_code,
            "next_attempt": next_attempt,
            "max_attempts": max_attempts,
        },
    )


def publish_human_approval_requested(
    runtime_run_id: str | None,
    *,
    section_key: str,
    review_score: float | None,
) -> RuntimeEvent | None:
    return publish_runtime_event(
        runtime_run_id,
        RuntimeEventType.APPROVAL_REQUESTED,
        "草稿已生成，等待人工审核。",
        {
            "capability": "human_approval",
            "section_key": section_key,
            "review_score": review_score,
        },
        once_key="human_approval_requested",
    )


def publish_human_approval_resolved(
    runtime_run_id: str | None,
    *,
    decision: str,
) -> RuntimeEvent | None:
    return publish_runtime_event(
        runtime_run_id,
        RuntimeEventType.APPROVAL_RESOLVED,
        "人工审核已处理。",
        {"capability": "human_approval", "decision": decision},
    )


def complete_runtime_run(
    runtime_run_id: str | None,
    *,
    result: dict[str, Any] | None = None,
) -> None:
    _finish_runtime_run(
        runtime_run_id,
        status="succeeded",
        event_type=RuntimeEventType.RUN_COMPLETED,
        summary="工作流已完成。",
        result=result,
    )


def cancel_runtime_run(runtime_run_id: str | None) -> None:
    _finish_runtime_run(
        runtime_run_id,
        status="cancelled",
        event_type=RuntimeEventType.RUN_CANCELLED,
        summary="工作流已取消。",
    )


def fail_runtime_run(
    runtime_run_id: str | None,
    message: str,
    *,
    error_code: str = "workflow_failed",
) -> None:
    _finish_runtime_run(
        runtime_run_id,
        status="failed",
        event_type=RuntimeEventType.RUN_FAILED,
        summary="工作流未能完成。",
        error_code=error_code,
        error_message=message,
    )


def find_runtime_run_id(execution_run_id: str) -> str | None:
    db = SessionLocal()
    try:
        return db.scalar(
            select(RuntimeRun.id)
            .where(RuntimeRun.execution_run_id == execution_run_id)
            .order_by(RuntimeRun.created_at.desc())
            .limit(1)
        )
    finally:
        db.close()


def is_runtime_cancellation_requested(runtime_run_id: str | None) -> bool:
    if not runtime_run_id:
        return False
    db = SessionLocal()
    try:
        status = db.scalar(select(RuntimeRun.status).where(RuntimeRun.id == runtime_run_id))
        return status in {"cancel_requested", "cancelled"}
    finally:
        db.close()


def publish_cancellation_detected(runtime_run_id: str | None, node_name: str) -> RuntimeEvent | None:
    return publish_runtime_event(
        runtime_run_id,
        RuntimeEventType.CAPABILITY_PROGRESSED,
        "已在安全边界停止工作流。",
        {"capability": node_name, "node": node_name, "phase": "cancellation_detected"},
        once_key="cancellation_detected",
    )


def redact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***redacted***" if _is_sensitive_key(key) else redact_payload(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return deepcopy(value)


def redact_text(value: str) -> str:
    redacted = value
    for pattern in _SECRET_TEXT_PATTERNS:
        redacted = pattern.sub("***redacted***", redacted)
    return redacted


def _finish_runtime_run(
    runtime_run_id: str | None,
    *,
    status: str,
    event_type: RuntimeEventType,
    summary: str,
    result: dict[str, Any] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    if not runtime_run_id:
        return
    db = SessionLocal()
    try:
        run = db.scalar(select(RuntimeRun).where(RuntimeRun.id == runtime_run_id).with_for_update())
        if run is None:
            raise ValueError(f"Runtime run {runtime_run_id} not found")
        if run.status == status:
            return
        if run.status in {"succeeded", "failed", "cancelled", "expired"}:
            return
        run.status = status
        run.result_json = redact_payload(result or {}) if result is not None else None
        run.error_code = error_code
        run.error_message = redact_text(error_message) if error_message else None
        run.finished_at = datetime.now(UTC).replace(tzinfo=None)
        latest = db.scalar(select(func.max(RuntimeEvent.sequence)).where(RuntimeEvent.run_id == run.id)) or 0
        db.add(
            RuntimeEvent(
                run_id=run.id,
                sequence=latest + 1,
                event_type=event_type.value,
                public_summary=summary,
                payload_json={"status": status, **({"error_code": error_code} if error_code else {})},
                schema_version="1.0",
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to finish runtime run", extra={"runtime_run_id": runtime_run_id})
        raise
    finally:
        db.close()


def _has_once_key(db, runtime_run_id: str, event_type: str, once_key: str) -> bool:
    events = db.scalars(
        select(RuntimeEvent).where(
            RuntimeEvent.run_id == runtime_run_id,
            RuntimeEvent.event_type == event_type,
        )
    )
    return any((event.payload_json or {}).get("event_key") == once_key for event in events)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in _SENSITIVE_KEY_MARKERS)


def _node_label(node_name: str) -> str:
    return {
        "supervisor": "执行规划",
        "rfp_parser": "招标需求解析",
        "knowledge_retriever": "证据检索",
        "section_drafter": "章节起草",
        "quality_reviewer": "质量审核",
        "human_approval": "人工审核",
        "memory_graph_extraction": "实体关系提取",
        "persist_result": "结果保存",
    }.get(node_name, "工作流步骤")
