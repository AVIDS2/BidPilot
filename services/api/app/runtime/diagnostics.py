"""Safe, queryable run diagnostics for the administrator operations plane.

The runtime event stream remains the user-facing progress surface.  This
module joins its durable records for support and incident triage without
returning prompts, tool arguments/results, provider credentials, or exception
messages.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from hashlib import sha256
import re
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.models import (
    AuditEvent,
    Deliverable,
    DeliverableSection,
    EvidenceSet,
    EvidenceSetItem,
    ExecutionRun,
    ModelUsageRecord,
    Project,
    RuntimeAction,
    RuntimeApproval,
    RuntimeEvent,
    RuntimeRun,
    SectionVersion,
    TaskOutboxEvent,
)

from .repository import get_visible_runtime_run
from .schemas import (
    RuntimeDiagnosticActionRead,
    RuntimeDiagnosticApprovalRead,
    RuntimeDiagnosticAuditEventRead,
    RuntimeDiagnosticDeliverableRead,
    RuntimeDiagnosticEventRead,
    RuntimeDiagnosticExecutionRunRead,
    RuntimeDiagnosticModelUsageRead,
    RuntimeDiagnosticRetrievalRead,
    RuntimeDiagnosticRetryRead,
    RuntimeDiagnosticTimingRead,
    RuntimeDiagnosticWorkerTaskRead,
    RuntimeDiagnosticsRead,
)


_MAX_EVENTS = 200
_MAX_LINKED_ROWS = 100
_MAX_AUDIT_SCAN = 500
_STALL_THRESHOLD_MS = 15 * 60 * 1000
_SAFE_ERROR_CODE = re.compile(r"^[a-z0-9][a-z0-9_:-]{0,99}$")


def get_runtime_diagnostics(
    db: Session,
    *,
    current_user: CurrentUser,
    run_id: str,
) -> RuntimeDiagnosticsRead:
    """Return an authorized, content-free correlation view for one run tree."""
    root = get_visible_runtime_run(db, run_id, current_user)
    now = _now()
    related_runs = _related_runtime_runs(db, root)
    runtime_run_ids = {item.id for item in related_runs}
    trace_ids = {item.trace_id for item in related_runs if item.trace_id}
    execution_runs = _related_execution_runs(db, root, related_runs)
    execution_run_ids = {item.id for item in execution_runs}

    event_count = int(
        db.scalar(
            select(func.count())
            .select_from(RuntimeEvent)
            .where(RuntimeEvent.run_id.in_(runtime_run_ids))
        )
        or 0
    )
    events = list(
        db.scalars(
            select(RuntimeEvent)
            .where(RuntimeEvent.run_id.in_(runtime_run_ids))
            .order_by(RuntimeEvent.created_at.asc(), RuntimeEvent.run_id.asc(), RuntimeEvent.sequence.asc())
            .limit(_MAX_EVENTS)
        ).all()
    )
    actions = list(
        db.scalars(
            select(RuntimeAction)
            .where(RuntimeAction.run_id.in_(runtime_run_ids))
            .order_by(RuntimeAction.created_at.asc(), RuntimeAction.id.asc())
            .limit(_MAX_LINKED_ROWS)
        ).all()
    )
    action_by_id = {action.id: action for action in actions}
    approvals = _related_approvals(db, action_by_id)
    project_ids = _related_project_ids(db, root, related_runs, execution_runs, actions)
    worker_tasks = _related_worker_tasks(db, root, runtime_run_ids, execution_run_ids)
    model_usage = _related_model_usage(db, root, runtime_run_ids, execution_run_ids)
    retrieval = _retrieval_summary(db, events, execution_run_ids)
    audit_events = _related_audit_events(db, project_ids, runtime_run_ids, trace_ids)
    deliverables = _related_deliverables(db, project_ids, execution_run_ids)
    retries = _retry_summary(events, execution_runs, worker_tasks)
    approval_wait = _approval_wait_from_events(events, now)
    error_code = _first_error_code(root, actions, worker_tasks)
    failure_category = _failure_category(root.status, error_code)
    timing = _timing(root.started_at or root.created_at, root.finished_at, now=now)
    provider_source = _provider_source(root)
    cost_status = "provider_cost_not_reported" if model_usage else "not_applicable"
    alerts = _alert_codes(
        root=root,
        timing=timing,
        failure_category=failure_category,
        worker_tasks=worker_tasks,
        retries=retries,
        cost_status=cost_status,
        retrieval=retrieval,
    )

    return RuntimeDiagnosticsRead(
        run_id=root.id,
        trace_id=root.trace_id,
        request_ref=_opaque_ref("request", root.idempotency_key),
        user_ref=_opaque_ref("user", root.user_id),
        org_ref=_opaque_ref("org", root.org_id),
        kind=root.kind,
        status=root.status,
        engine=root.engine,
        project_id=root.project_id or (project_ids[0] if project_ids else None),
        conversation_id=root.conversation_id,
        execution_run_id=root.execution_run_id,
        parent_run_id=root.parent_run_id,
        model=root.model,
        reasoning_effort=root.reasoning_effort,
        provider_source=provider_source,
        timing=timing,
        error_code=error_code,
        failure_category=failure_category,
        cancellation_requested=root.status in {"cancel_requested", "cancelled"},
        retries=retries,
        approval_wait_duration_ms=approval_wait,
        actions=[
            RuntimeDiagnosticActionRead(
                action_id=action.id,
                capability=action.capability_name,
                status=action.status,
                risk_level=action.risk_level,
                policy_outcome=action.policy_outcome,
                approval_mode=action.approval_mode,
                public_summary=_diagnostic_action_summary(action.status),
                error_code=_safe_error_code(action.error_code),
                created_at=action.created_at,
                completed_at=action.completed_at,
                duration_ms=_duration_ms(action.created_at, action.completed_at, now=now),
            )
            for action in actions
        ],
        approvals=[
            RuntimeDiagnosticApprovalRead(
                approval_id=approval.id,
                action_id=approval.action_id,
                capability=action_by_id[approval.action_id].capability_name,
                status=approval.status,
                decision=_safe_decision(approval.decision_json),
                created_at=approval.created_at,
                expires_at=approval.expires_at,
                resolved_at=approval.resolved_at,
                wait_duration_ms=_approval_wait_duration(approval, now),
            )
            for approval in approvals
        ],
        event_count=event_count,
        events_truncated=event_count > len(events),
        events=[
            RuntimeDiagnosticEventRead(
                event_id=event.id,
                run_id=event.run_id,
                sequence=event.sequence,
                type=event.event_type,
                public_summary=_diagnostic_event_summary(event.event_type),
                timestamp=event.created_at,
            )
            for event in events
        ],
        execution_runs=[
            RuntimeDiagnosticExecutionRunRead(
                execution_run_id=execution_run.id,
                parent_execution_run_id=execution_run.parent_execution_run_id,
                run_type=execution_run.run_type,
                status=execution_run.status,
                attempt_number=execution_run.attempt_number,
                timing=_timing(execution_run.started_at, execution_run.finished_at, now=now),
            )
            for execution_run in execution_runs
        ],
        worker_tasks=[
            RuntimeDiagnosticWorkerTaskRead(
                task_name=task.task_name,
                status=task.status,
                dispatch_attempts=task.dispatch_attempts,
                delivery_attempts=task.delivery_attempts,
                last_error_code=_safe_error_code(task.last_error_code),
                created_at=task.created_at,
                dispatched_at=task.dispatched_at,
                completed_at=task.completed_at,
                duration_ms=_duration_ms(task.created_at, task.completed_at, now=now),
            )
            for task in worker_tasks
        ],
        model_usage=model_usage,
        cost_status=cost_status,
        retrieval=retrieval,
        audit_events=audit_events,
        deliverables=deliverables,
        alert_codes=alerts,
    )


def _related_runtime_runs(db: Session, root: RuntimeRun) -> list[RuntimeRun]:
    children = list(
        db.scalars(
            select(RuntimeRun)
            .where(
                RuntimeRun.parent_run_id == root.id,
                RuntimeRun.org_id == root.org_id,
            )
            .order_by(RuntimeRun.created_at.asc(), RuntimeRun.id.asc())
            .limit(_MAX_LINKED_ROWS - 1)
        ).all()
    )
    return [root, *children]


def _related_execution_runs(
    db: Session,
    root: RuntimeRun,
    runtime_runs: list[RuntimeRun],
) -> list[ExecutionRun]:
    direct_ids = {run.execution_run_id for run in runtime_runs if run.execution_run_id}
    if not direct_ids:
        return []

    rows = list(
        db.scalars(
            select(ExecutionRun)
            .join(Project, Project.id == ExecutionRun.project_id)
            .where(
                ExecutionRun.id.in_(direct_ids),
                Project.org_id == root.org_id,
            )
        ).all()
    )
    if root.project_id is not None:
        rows = [row for row in rows if row.project_id == root.project_id]

    known = {row.id for row in rows}
    frontier = list(known)
    while frontier and len(known) < _MAX_LINKED_ROWS:
        children = list(
            db.scalars(
                select(ExecutionRun)
                .join(Project, Project.id == ExecutionRun.project_id)
                .where(
                    ExecutionRun.parent_execution_run_id.in_(frontier),
                    Project.org_id == root.org_id,
                )
                .limit(_MAX_LINKED_ROWS - len(known))
            ).all()
        )
        frontier = []
        for child in children:
            if child.id in known or (root.project_id is not None and child.project_id != root.project_id):
                continue
            known.add(child.id)
            frontier.append(child.id)
            rows.append(child)
    return sorted(rows, key=lambda row: (row.attempt_number, row.id))


def _related_project_ids(
    db: Session,
    root: RuntimeRun,
    runtime_runs: list[RuntimeRun],
    execution_runs: list[ExecutionRun],
    actions: list[RuntimeAction],
) -> list[str]:
    """Resolve only same-org project links already owned by the run trace."""
    candidates: list[str] = []
    for run in runtime_runs:
        if run.project_id and run.project_id not in candidates:
            candidates.append(run.project_id)
    for execution_run in execution_runs:
        if execution_run.project_id not in candidates:
            candidates.append(execution_run.project_id)
    for action in actions:
        if action.capability_name != "create_project" or action.status != "succeeded":
            continue
        project_id = (action.result_json or {}).get("id")
        if isinstance(project_id, str) and project_id not in candidates:
            candidates.append(project_id)
    if not candidates:
        return []

    authorized_ids = set(
        db.scalars(
            select(Project.id).where(
                Project.id.in_(candidates),
                Project.org_id == root.org_id,
            )
        ).all()
    )
    return [project_id for project_id in candidates if project_id in authorized_ids]


def _related_approvals(
    db: Session,
    action_by_id: dict[str, RuntimeAction],
) -> list[RuntimeApproval]:
    if not action_by_id:
        return []
    return list(
        db.scalars(
            select(RuntimeApproval)
            .where(RuntimeApproval.action_id.in_(list(action_by_id)))
            .order_by(RuntimeApproval.created_at.asc(), RuntimeApproval.id.asc())
            .limit(_MAX_LINKED_ROWS)
        ).all()
    )


def _related_worker_tasks(
    db: Session,
    root: RuntimeRun,
    runtime_run_ids: set[str],
    execution_run_ids: set[str],
) -> list[TaskOutboxEvent]:
    clauses = [TaskOutboxEvent.runtime_run_id.in_(runtime_run_ids)]
    if execution_run_ids:
        clauses.append(TaskOutboxEvent.execution_run_id.in_(execution_run_ids))
    return list(
        db.scalars(
            select(TaskOutboxEvent)
            .where(TaskOutboxEvent.org_id == root.org_id, or_(*clauses))
            .order_by(TaskOutboxEvent.created_at.asc(), TaskOutboxEvent.id.asc())
            .limit(_MAX_LINKED_ROWS)
        ).all()
    )


def _related_model_usage(
    db: Session,
    root: RuntimeRun,
    runtime_run_ids: set[str],
    execution_run_ids: set[str],
) -> list[RuntimeDiagnosticModelUsageRead]:
    clauses = [ModelUsageRecord.runtime_run_id.in_(runtime_run_ids)]
    if execution_run_ids:
        clauses.append(ModelUsageRecord.execution_run_id.in_(execution_run_ids))
    records = list(
        db.scalars(
            select(ModelUsageRecord)
            .where(ModelUsageRecord.org_id == root.org_id, or_(*clauses))
            .order_by(ModelUsageRecord.created_at.asc(), ModelUsageRecord.id.asc())
            .limit(_MAX_LINKED_ROWS)
        ).all()
    )
    grouped: dict[tuple[str, str, str, str], dict[str, int]] = defaultdict(
        lambda: {
            "call_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "total_tokens": 0,
        }
    )
    for record in records:
        key = (record.provider_source, record.provider_type, record.model_name, record.workload)
        aggregate = grouped[key]
        aggregate["call_count"] += 1
        for field in (
            "input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "cache_read_tokens",
            "cache_write_tokens",
            "total_tokens",
        ):
            aggregate[field] += int(getattr(record, field) or 0)
    return [
        RuntimeDiagnosticModelUsageRead(
            provider_source=provider_source,
            provider_type=provider_type,
            model_name=model_name,
            workload=workload,
            call_count=values["call_count"],
            input_tokens=values["input_tokens"],
            output_tokens=values["output_tokens"],
            reasoning_tokens=values["reasoning_tokens"],
            cache_read_tokens=values["cache_read_tokens"],
            cache_write_tokens=values["cache_write_tokens"],
            total_tokens=values["total_tokens"],
            cost_status="provider_cost_not_reported",
        )
        for (provider_source, provider_type, model_name, workload), values in sorted(grouped.items())
    ]


def _retrieval_summary(
    db: Session,
    events: list[RuntimeEvent],
    execution_run_ids: set[str],
) -> RuntimeDiagnosticRetrievalRead:
    attempts = 0
    candidates: list[int] = []
    fused: list[int] = []
    reranked: list[int] = []
    evidence_hits: list[int] = []
    latencies: list[int] = []
    for event in events:
        payload = event.payload_json if isinstance(event.payload_json, dict) else {}
        if event.event_type != "capability.succeeded" or payload.get("capability") != "knowledge_retriever":
            continue
        attempts += 1
        _append_nonnegative(candidates, payload.get("retrieval_candidate_count"))
        _append_nonnegative(fused, payload.get("retrieval_fused_candidate_count"))
        _append_nonnegative(reranked, payload.get("retrieval_reranked_candidate_count"))
        _append_nonnegative(evidence_hits, payload.get("evidence_count"))
        _append_nonnegative(latencies, payload.get("retrieval_latency_ms"))

    evidence_set_count = 0
    degraded_evidence_set_count = 0
    evidence_item_count: int | None = None
    if execution_run_ids:
        evidence_sets = list(
            db.scalars(
                select(EvidenceSet)
                .where(EvidenceSet.execution_run_id.in_(execution_run_ids))
                .limit(_MAX_LINKED_ROWS)
            ).all()
        )
        evidence_set_count = len(evidence_sets)
        degraded_evidence_set_count = sum(item.status != "ready" for item in evidence_sets)
        evidence_set_ids = [item.id for item in evidence_sets]
        if evidence_set_ids:
            evidence_item_count = int(
                db.scalar(
                    select(func.count())
                    .select_from(EvidenceSetItem)
                    .where(EvidenceSetItem.evidence_set_id.in_(evidence_set_ids))
                )
                or 0
            )

    return RuntimeDiagnosticRetrievalRead(
        retrieval_attempt_count=attempts,
        candidate_count=sum(candidates) if candidates else None,
        fused_candidate_count=sum(fused) if fused else None,
        reranked_candidate_count=sum(reranked) if reranked else None,
        evidence_hit_count=sum(evidence_hits) if evidence_hits else evidence_item_count,
        evidence_set_count=evidence_set_count,
        retrieval_latency_ms=sum(latencies) if latencies else None,
        degraded_evidence_set_count=degraded_evidence_set_count,
    )


def _related_audit_events(
    db: Session,
    project_ids: list[str],
    runtime_run_ids: set[str],
    trace_ids: set[str],
) -> list[RuntimeDiagnosticAuditEventRead]:
    if not project_ids:
        return []
    rows = list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.project_id.in_(project_ids))
            .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
            .limit(_MAX_AUDIT_SCAN)
        ).all()
    )
    result: list[RuntimeDiagnosticAuditEventRead] = []
    for event in rows:
        payload = event.payload_json if isinstance(event.payload_json, dict) else {}
        if payload.get("runtime_run_id") not in runtime_run_ids and payload.get("trace_id") not in trace_ids:
            continue
        result.append(
            RuntimeDiagnosticAuditEventRead(
                event_id=event.id,
                event_type=event.event_type,
                created_at=event.created_at,
            )
        )
    return result[:_MAX_LINKED_ROWS]


def _related_deliverables(
    db: Session,
    project_ids: list[str],
    execution_run_ids: set[str],
) -> list[RuntimeDiagnosticDeliverableRead]:
    if not project_ids or not execution_run_ids:
        return []
    rows = db.execute(
        select(SectionVersion, DeliverableSection, Deliverable)
        .join(DeliverableSection, DeliverableSection.id == SectionVersion.deliverable_section_id)
        .join(Deliverable, Deliverable.id == DeliverableSection.deliverable_id)
        .where(
            SectionVersion.generation_run_id.in_(execution_run_ids),
            Deliverable.project_id.in_(project_ids),
        )
        .order_by(Deliverable.title.asc(), DeliverableSection.sort_order.asc(), SectionVersion.version_number.asc())
        .limit(_MAX_LINKED_ROWS)
    ).all()
    return [
        RuntimeDiagnosticDeliverableRead(
            deliverable_id=deliverable.id,
            deliverable_title=deliverable.title,
            deliverable_status=deliverable.status,
            section_version_id=version.id,
            section_key=section.section_key,
            section_title=section.title,
            section_status=section.status,
            version_number=version.version_number,
        )
        for version, section, deliverable in rows
    ]


def _retry_summary(
    events: list[RuntimeEvent],
    execution_runs: list[ExecutionRun],
    worker_tasks: list[TaskOutboxEvent],
) -> RuntimeDiagnosticRetryRead:
    provider_retries = sum(
        1
        for event in events
        if event.event_type == "capability.progressed"
        and isinstance(event.payload_json, dict)
        and event.payload_json.get("phase") == "provider_retry"
    )
    execution_retries = sum(max(run.attempt_number - 1, 0) for run in execution_runs)
    task_redeliveries = sum(
        max(task.dispatch_attempts - 1, 0) + max(task.delivery_attempts - 1, 0)
        for task in worker_tasks
    )
    return RuntimeDiagnosticRetryRead(
        execution_retries=execution_retries,
        provider_retries=provider_retries,
        task_redeliveries=task_redeliveries,
        total=execution_retries + provider_retries + task_redeliveries,
    )


def _approval_wait_from_events(events: list[RuntimeEvent], now: datetime) -> int:
    pending_at: datetime | None = None
    total = 0
    for event in events:
        if event.event_type == "approval.requested":
            pending_at = event.created_at
        elif event.event_type == "approval.resolved" and pending_at is not None:
            total += _duration_ms(pending_at, event.created_at, now=now) or 0
            pending_at = None
    if pending_at is not None:
        total += _duration_ms(pending_at, None, now=now) or 0
    return total


def _approval_wait_duration(approval: RuntimeApproval, now: datetime) -> int:
    end = approval.resolved_at
    if end is None and approval.status in {"expired", "cancelled"}:
        end = approval.expires_at
    return _duration_ms(approval.created_at, end, now=now) or 0


def _first_error_code(
    root: RuntimeRun,
    actions: list[RuntimeAction],
    worker_tasks: list[TaskOutboxEvent],
) -> str | None:
    candidates: list[str | None] = [root.error_code]
    candidates.extend(action.error_code for action in actions if action.status == "failed")
    candidates.extend(task.last_error_code for task in worker_tasks if task.status == "failed")
    for candidate in candidates:
        safe = _safe_error_code(candidate)
        if safe:
            return safe
    return None


def _failure_category(status: str, error_code: str | None) -> str | None:
    if status in {"cancel_requested", "cancelled"}:
        return "cancelled"
    if status != "failed" and error_code is None:
        return None
    code = error_code or "unknown"
    if any(marker in code for marker in ("approval", "confirmation")):
        return "approval"
    if any(marker in code for marker in ("permission", "access", "capability_policy", "forbidden")):
        return "authorization"
    if any(marker in code for marker in ("budget", "quota", "limit")):
        return "quota"
    if any(marker in code for marker in ("provider", "model", "embedding")):
        return "provider"
    if any(marker in code for marker in ("invalid", "required", "missing", "input")):
        return "input"
    if any(marker in code for marker in ("timeout", "unavailable", "retry")):
        return "transient"
    if any(marker in code for marker in ("workflow", "task", "worker")):
        return "worker"
    return "internal"


def _alert_codes(
    *,
    root: RuntimeRun,
    timing: RuntimeDiagnosticTimingRead,
    failure_category: str | None,
    worker_tasks: list[TaskOutboxEvent],
    retries: RuntimeDiagnosticRetryRead,
    cost_status: str,
    retrieval: RuntimeDiagnosticRetrievalRead,
) -> list[str]:
    alerts: list[str] = []
    if root.status == "failed":
        alerts.append(f"runtime_failed_{failure_category or 'unknown'}")
    if (
        root.status in {"queued", "running", "cancel_requested"}
        and timing.duration_ms is not None
        and timing.duration_ms >= _STALL_THRESHOLD_MS
    ):
        alerts.append("runtime_stalled")
    if any(task.status == "failed" for task in worker_tasks):
        alerts.append("worker_task_failed")
    if retries.total > 0:
        alerts.append("retry_observed")
    if cost_status == "provider_cost_not_reported":
        alerts.append("provider_cost_not_reported")
    if retrieval.retrieval_attempt_count > 0 and retrieval.candidate_count is None:
        alerts.append("retrieval_candidate_metrics_missing")
    return alerts


def _provider_source(run: RuntimeRun) -> str:
    configured = (run.input_json or {}).get("provider_source")
    if configured in {"official", "byok", "stub"}:
        return configured
    return "byok" if run.provider_config_id else "official"


def _timing(started_at: datetime | None, finished_at: datetime | None, *, now: datetime) -> RuntimeDiagnosticTimingRead:
    return RuntimeDiagnosticTimingRead(
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=_duration_ms(started_at, finished_at, now=now),
    )


def _duration_ms(started_at: datetime | None, finished_at: datetime | None, *, now: datetime) -> int | None:
    if started_at is None:
        return None
    start = _naive_utc(started_at)
    end = _naive_utc(finished_at or now)
    return max(int((end - start).total_seconds() * 1000), 0)


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _append_nonnegative(target: list[int], value: Any) -> None:
    if type(value) is int and value >= 0:
        target.append(value)


def _opaque_ref(prefix: str, value: str | None) -> str | None:
    if not value:
        return None
    return f"{prefix}_{sha256(value.encode('utf-8')).hexdigest()[:12]}"


def _safe_error_code(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized if _SAFE_ERROR_CODE.fullmatch(normalized) else "internal_error_code_redacted"


def _diagnostic_action_summary(status: str) -> str:
    return {
        "succeeded": "操作已完成。",
        "failed": "操作未完成。",
        "awaiting_approval": "操作等待审批。",
        "cancelled": "操作已取消。",
        "expired": "操作审批已过期。",
        "running": "操作正在执行。",
    }.get(status, "操作状态已记录。")


def _diagnostic_event_summary(event_type: str) -> str:
    """Return an operational label without replaying user/model content."""
    return {
        "run.started": "运行已开始。",
        "run.completed": "运行已完成。",
        "run.failed": "运行未完成。",
        "run.cancelled": "运行已取消。",
        "capability.started": "能力步骤已开始。",
        "capability.succeeded": "能力步骤已完成。",
        "capability.failed": "能力步骤未完成。",
        "capability.progressed": "能力步骤已更新。",
        "approval.requested": "审批已请求。",
        "approval.resolved": "审批已处理。",
        "message.completed": "面向用户的回复已生成。",
    }.get(event_type, "运行事件已记录。")


def _safe_decision(value: dict | None) -> str | None:
    if not isinstance(value, dict):
        return None
    decision = value.get("decision")
    return decision if decision in {"approve", "edit", "reject", "cancel"} else None


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
