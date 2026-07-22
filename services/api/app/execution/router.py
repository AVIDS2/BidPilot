from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .schemas import ExecutionRunRead
from .service import get_run_query, list_runs_query, retry_failed_run_command

router = APIRouter(prefix="/execution", tags=["execution"])


@router.get("/runs/{run_id}", response_model=ExecutionRunRead)
def get_execution_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> ExecutionRunRead:
    return get_run_query(db, run_id, current_user)


@router.get("/runs", response_model=list[ExecutionRunRead])
def list_execution_runs(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[ExecutionRunRead]:
    return list_runs_query(db, project_id, current_user)


@router.post("/runs/{run_id}/retry", response_model=ExecutionRunRead)
def retry_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> ExecutionRunRead:
    return retry_failed_run_command(db, run_id, current_user)
