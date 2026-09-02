"""Persistence helpers for governed runtime records."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import and_, false, or_, select
from sqlalchemy.orm import Session

from app.access.service import list_accessible_projects, require_project_capability
from app.auth.schemas import CurrentUser
from app.models import ChatTaskState, Project, RuntimeAction, RuntimeApproval, RuntimeEvent, RuntimeRun, TaskOutboxEvent
from contracts.runtime import RuntimeApprovalStatus, RuntimeRunStatus

from .pi_control import is_pi_execution_active


_OPEN_RUN_STATUSES = {
    RuntimeRunStatus.QUEUED.value,
    RuntimeRunStatus.RUNNING.value,
    RuntimeRunStatus.AWAITING_APPROVAL.value,
    RuntimeRunStatus.AWAITING_INPUT.value,
    RuntimeRunStatus.CANCEL_REQUESTED.value,
}
_TERMINAL_OUTBOX_STATUSES = {"completed", "failed", "cancelled"}
_OUTBOX_LEASE_GRACE = timedelta(hours=1)
_ASSISTANT_STALE_AFTER = timedelta(minutes=30)
_WORKFLOW_STALE_AFTER = timedelta(hours=1)
_INPUT_STALE_AFTER = timedelta(minutes=30)
_CANCEL_STALE_AFTER = timedelta(minutes=10)
_RECENT_COMPLETED_AFTER = timedelta(days=14)


@dataclass(frozen=True)
class RuntimeRunListRow:
    """A deliberately small, already-authorized row for the Run Center."""

    run: RuntimeRun
    project_name: str | None
    latest_event_summary: str | None


def get_runtime_run_for_update(db: Session, run_id: str) -> RuntimeRun | None:
    return db.scalar(select(RuntimeRun).where(RuntimeRun.id == run_id).with_for_update())


def get_visible_runtime_run(db: Session, run_id: str, current_user: CurrentUser) -> RuntimeRun:
    run = db.get(RuntimeRun, run_id)
    if run is None or run.org_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Runtime run not found")

    if run.project_id:
        require_project_capability(
            db,
            current_user=current_user,
            project_id=run.project_id,
            capability="project.read",
        )
    elif run.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=404, detail="Runtime run not found")

    return run


def list_visible_runtime_runs(
    db: Session,
    *,
    current_user: CurrentUser,
    limit: int,
    conversation_id: str | None = None,
    kinds: Sequence[str] | None = None,
    live_only: bool = False,
) -> list[RuntimeRunListRow]:
    """List only RuntimeRuns that the caller can already open individually.

    This deliberately mirrors ``get_visible_runtime_run`` instead of treating
    organization membership as permission to enumerate every project run.
    """

    latest_event_summary = (
        select(RuntimeEvent.public_summary)
        .where(RuntimeEvent.run_id == RuntimeRun.id)
        .order_by(RuntimeEvent.sequence.desc())
        .limit(1)
        .scalar_subquery()
    )
    stmt = (
        select(
            RuntimeRun,
            Project.name.label("project_name"),
            latest_event_summary.label("latest_event_summary"),
        )
        .outerjoin(Project, Project.id == RuntimeRun.project_id)
        .where(
            RuntimeRun.org_id == (current_user.org_id or "default"),
            or_(RuntimeRun.project_id.is_(None), Project.status != "deleted"),
        )
    )
    if conversation_id:
        stmt = stmt.where(RuntimeRun.conversation_id == conversation_id)
    if kinds:
        stmt = stmt.where(RuntimeRun.kind.in_(tuple(kinds)))

    if current_user.role != "admin":
        accessible_project_ids = [
            project.id
            for project in list_accessible_projects(db, current_user=current_user)
        ]
        visible_project_runs = (
            RuntimeRun.project_id.in_(accessible_project_ids)
            if accessible_project_ids
            else false()
        )
        own_global_runs = and_(
            RuntimeRun.project_id.is_(None),
            RuntimeRun.user_id == current_user.id,
        )
        stmt = stmt.where(or_(visible_project_runs, own_global_runs))

    # The user-facing work overview must not infer liveness from a stale
    # database status. Keep open rows available for the session/outbox checks,
    # but exclude terminal history older than the recent-completion window
    # before applying the in-process liveness rules. The bounded prefetch is
    # deliberately larger than the response limit so stale open rows cannot
    # hide a recent completed task in a busy workspace.
    if live_only:
        recent_completed_cutoff = datetime.now(UTC).replace(tzinfo=None) - _RECENT_COMPLETED_AFTER
        stmt = stmt.where(
            or_(
                RuntimeRun.status.in_(tuple(_OPEN_RUN_STATUSES)),
                RuntimeRun.created_at.is_(None),
                RuntimeRun.created_at >= recent_completed_cutoff,
            )
        )
    fetch_limit = min(400, max(limit, limit * 4)) if live_only else limit
    rows = db.execute(stmt.order_by(RuntimeRun.created_at.desc()).limit(fetch_limit)).all()
    if live_only:
        rows = _filter_live_runtime_rows(db, rows, limit=limit)
    return [
        RuntimeRunListRow(
            run=run,
            project_name=project_name,
            latest_event_summary=event_summary,
        )
        for run, project_name, event_summary in rows
    ]


def _filter_live_runtime_rows(
    db: Session,
    rows: list[tuple[RuntimeRun, str | None, str | None]],
    *,
    limit: int,
) -> list[tuple[RuntimeRun, str | None, str | None]]:
    if not rows:
        return []

    current = datetime.now(UTC).replace(tzinfo=None)
    run_ids = [run.id for run, _project_name, _summary in rows]
    outbox_by_run: dict[str, list[TaskOutboxEvent]] = {run_id: [] for run_id in run_ids}
    for outbox in db.scalars(
        select(TaskOutboxEvent).where(TaskOutboxEvent.runtime_run_id.in_(run_ids))
    ):
        if outbox.runtime_run_id:
            outbox_by_run[outbox.runtime_run_id].append(outbox)

    pending_approval_run_ids = {
        run_id
        for (run_id,) in db.execute(
            select(RuntimeAction.run_id)
            .join(RuntimeApproval, RuntimeApproval.action_id == RuntimeAction.id)
            .where(
                RuntimeAction.run_id.in_(run_ids),
                RuntimeApproval.status == RuntimeApprovalStatus.PENDING.value,
                RuntimeApproval.expires_at > current,
            )
        )
    }
    input_states = {
        state.conversation_id: state
        for state in db.scalars(
            select(ChatTaskState).where(ChatTaskState.conversation_id.in_(
                run.conversation_id for run, _project_name, _summary in rows if run.conversation_id
            ))
        )
    }

    filtered: list[tuple[RuntimeRun, str | None, str | None]] = []
    for row in rows:
        run = row[0]
        if _is_live_runtime_run(
            run,
            current=current,
            outbox_rows=outbox_by_run[run.id],
            pending_approval=run.id in pending_approval_run_ids,
            input_state=input_states.get(run.conversation_id) if run.conversation_id else None,
        ):
            filtered.append(row)
        if len(filtered) >= limit:
            break
    return filtered


def _is_live_runtime_run(
    run: RuntimeRun,
    *,
    current: datetime,
    outbox_rows: list[TaskOutboxEvent],
    pending_approval: bool,
    input_state: ChatTaskState | None,
) -> bool:
    if run.status not in _OPEN_RUN_STATUSES:
        # The overview's completed section is intentionally recent and
        # bounded. Older terminal history belongs in the administrator view.
        return _is_recent(run, current, _RECENT_COMPLETED_AFTER)

    if run.status == RuntimeRunStatus.AWAITING_APPROVAL.value:
        return pending_approval or _is_recent(run, current, _WORKFLOW_STALE_AFTER)

    if run.status == RuntimeRunStatus.AWAITING_INPUT.value:
        if (
            input_state is not None
            and input_state.status == "needs_input"
            and input_state.updated_at is not None
            and current - input_state.updated_at < _INPUT_STALE_AFTER
        ):
            return True
        return _is_recent(run, current, _INPUT_STALE_AFTER)

    stale_after = _ASSISTANT_STALE_AFTER if run.kind == "assistant_turn" else _WORKFLOW_STALE_AFTER
    if _has_live_outbox(outbox_rows, current, stale_after=stale_after):
        return True
    if run.engine == "pi" and is_pi_execution_active(run.id):
        return True
    if run.status == RuntimeRunStatus.CANCEL_REQUESTED.value:
        return _is_recent(run, current, _CANCEL_STALE_AFTER)
    return _is_recent(run, current, stale_after)


def _is_recent(run: RuntimeRun, current: datetime, stale_after: timedelta) -> bool:
    created_at = run.created_at or current
    return current - created_at < stale_after


def _has_live_outbox(
    rows: list[TaskOutboxEvent],
    current: datetime,
    *,
    stale_after: timedelta,
) -> bool:
    for row in rows:
        if row.status in _TERMINAL_OUTBOX_STATUSES:
            continue
        if row.status == "pending":
            # A pending outbox row is only a recent delivery intent. Without
            # a worker lease, an old row is historical residue, not evidence
            # that a background task is still running.
            if _is_recent_timestamp(row.created_at, current, stale_after):
                return True
            continue
        if row.lease_expires_at is None:
            if _is_recent_timestamp(row.created_at, current, stale_after):
                return True
            continue
        if row.lease_expires_at > current - _OUTBOX_LEASE_GRACE:
            return True
    return False


def _is_recent_timestamp(
    value: datetime | None,
    current: datetime,
    stale_after: timedelta,
) -> bool:
    return value is None or current - value < stale_after
