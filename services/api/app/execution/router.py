from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db

from .schemas import ExecutionRunRead
from .service import get_run_query, list_runs_query, retry_failed_run_command

router = APIRouter(prefix="/execution", tags=["execution"])


@router.get("/runs/{run_id}", response_model=ExecutionRunRead)
def get_execution_run(run_id: str, db: Session = Depends(get_db)) -> ExecutionRunRead:
    result = get_run_query(db, run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Execution run not found")
    return result


@router.get("/runs", response_model=list[ExecutionRunRead])
def list_execution_runs(project_id: str, db: Session = Depends(get_db)) -> list[ExecutionRunRead]:
    return list_runs_query(db, project_id)


@router.post("/runs/{run_id}/retry", response_model=ExecutionRunRead)
def retry_run(run_id: str, db: Session = Depends(get_db)) -> ExecutionRunRead:
    return retry_failed_run_command(db, run_id)
