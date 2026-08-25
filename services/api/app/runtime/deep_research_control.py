"""Durable control-plane handoff for the generic Deep Research workflow.

Pi only starts a research run. The Worker owns the multi-stage investigation,
source/evidence ledger and report synthesis; the parent conversation receives a
normal system wake when the child becomes terminal.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.models import RuntimeRun
from app.outbox.service import enqueue_workflow_task, request_task_outbox_dispatch
from contracts.runtime import RuntimeEventType, RuntimeRunKind, RuntimeRunStatus

from .events import RuntimeEventDraft, append_events
from .repository import get_visible_runtime_run
from .service import create_runtime_run, find_idempotent_runtime_run

_DEPTH_LIMITS: dict[str, dict[str, int]] = {
    "quick": {"max_queries": 3, "max_sources": 6},
    "standard": {"max_queries": 5, "max_sources": 10},
    "deep": {"max_queries": 8, "max_sources": 16},
}


def create_deep_research_run(
    db: Session,
    user: CurrentUser,
    *,
    parent_run_id: str,
    tool_call_id: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    parent = get_visible_runtime_run(db, parent_run_id, user)
    if parent is None or parent.status not in {
        RuntimeRunStatus.RUNNING.value,
        RuntimeRunStatus.AWAITING_APPROVAL.value,
    }:
        raise ValueError("deep_research_parent_not_executable")

    query = str(arguments.get("query") or "").strip()
    if not query or len(query) > 12_000:
        raise ValueError("deep_research_query_invalid")
    depth = str(arguments.get("depth") or "standard").strip().lower()
    if depth not in _DEPTH_LIMITS:
        raise ValueError("deep_research_depth_invalid")
    source_policy = str(arguments.get("source_policy") or "official_first").strip().lower()
    if source_policy not in {"official_first", "open_web"}:
        raise ValueError("deep_research_source_policy_invalid")
    requested_project_id = str(arguments.get("project_id") or "").strip() or None
    if requested_project_id and parent.project_id and requested_project_id != parent.project_id:
        raise ValueError("deep_research_project_scope_invalid")
    project_id = requested_project_id or parent.project_id
    limits = _DEPTH_LIMITS[depth]
    idempotency_key = f"deep-research:{parent.id}:{tool_call_id}"
    existing = find_idempotent_runtime_run(db, user, idempotency_key=idempotency_key)
    if existing is not None:
        return _result(existing, depth=depth, source_policy=source_policy, duplicate=True)

    child = create_runtime_run(
        db,
        user,
        kind=RuntimeRunKind.DEEP_RESEARCH.value,
        engine="deep_research_worker",
        project_id=project_id,
        conversation_id=parent.conversation_id,
        parent_run_id=parent.id,
        provider_config_id=parent.provider_config_id,
        model=parent.model,
        reasoning_effort=parent.reasoning_effort,
        approval_mode=str((parent.policy_snapshot_json or {}).get("approval_mode") or "risky_only"),
        idempotency_key=idempotency_key,
        input_json={
            "query": query,
            "depth": depth,
            "source_policy": source_policy,
            "max_queries": limits["max_queries"],
            "max_sources": limits["max_sources"],
            "parent_run_id": parent.id,
            "tool_call_id": tool_call_id,
            "presentation_kind": "deep_research",
            "presentation_title": "深度调研",
        },
        initial_status=RuntimeRunStatus.QUEUED.value,
        commit=False,
    )
    outbox = enqueue_workflow_task(
        db,
        org_id=user.org_id,
        project_id=project_id,
        execution_run_id=None,
        runtime_run_id=child.id,
        task_name="worker.run_deep_research",
        args=[child.id],
        kwargs={},
        deduplication_key=f"deep-research:{child.id}",
    )
    append_events(
        db,
        parent.id,
        [
            RuntimeEventDraft(
                type=RuntimeEventType.WORKFLOW_LINKED,
                public_summary="已创建深度调研运行任务。",
                payload={
                    "workflow_runtime_run_id": child.id,
                    "research_run_id": child.id,
                    "presentation_kind": "deep_research",
                    "presentation_session_id": child.id,
                    "presentation_title": "深度调研",
                },
            )
        ],
    )
    db.commit()
    request_task_outbox_dispatch(outbox.id)
    return _result(child, depth=depth, source_policy=source_policy, duplicate=False)


def _result(run: RuntimeRun, *, depth: str, source_policy: str, duplicate: bool) -> dict[str, Any]:
    return {
        "research_run_id": run.id,
        "runtime_run_id": run.id,
        "trace_id": run.trace_id,
        "status": run.status,
        "depth": depth,
        "source_policy": source_policy,
        "presentation_kind": "deep_research",
        "presentation_title": "深度调研",
        "resumable": True,
        "duplicate": duplicate,
        "next_step": "wait_for_research_updates",
    }


__all__ = ["create_deep_research_run"]
