from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExecutionRun


def get_run(db: Session, run_id: str) -> ExecutionRun | None:
    return db.get(ExecutionRun, run_id)


def list_runs_by_project(db: Session, project_id: str) -> list[ExecutionRun]:
    stmt = select(ExecutionRun).where(ExecutionRun.project_id == project_id).order_by(ExecutionRun.started_at.desc())
    return list(db.scalars(stmt).all())
