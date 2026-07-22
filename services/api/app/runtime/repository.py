"""Persistence helpers for governed runtime records."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import and_, false, or_, select
from sqlalchemy.orm import Session

from app.access.service import list_accessible_projects, require_project_capability
from app.auth.schemas import CurrentUser
from app.models import Project, RuntimeEvent, RuntimeRun


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

    rows = db.execute(
        stmt.order_by(RuntimeRun.created_at.desc()).limit(limit)
    ).all()
    return [
        RuntimeRunListRow(
            run=run,
            project_name=project_name,
            latest_event_summary=event_summary,
        )
        for run, project_name, event_summary in rows
    ]
