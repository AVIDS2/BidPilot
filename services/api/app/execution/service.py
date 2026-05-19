from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.audit.service import record_audit_event
from app.celery_client import celery

from .repository import get_run, list_runs_by_project
from .schemas import ExecutionRunRead


def get_run_query(db: Session, run_id: str) -> ExecutionRunRead | None:
    run = get_run(db, run_id)
    if run is None:
        return None
    return ExecutionRunRead(id=run.id, project_id=run.project_id, run_type=run.run_type, status=run.status, input_json=run.input_json, output_json=run.output_json)


def list_runs_query(db: Session, project_id: str) -> list[ExecutionRunRead]:
    runs = list_runs_by_project(db, project_id)
    return [ExecutionRunRead(id=r.id, project_id=r.project_id, run_type=r.run_type, status=r.status, input_json=r.input_json, output_json=r.output_json) for r in runs]


def retry_failed_run_command(db: Session, run_id: str) -> ExecutionRunRead:
    """Retry a failed execution run by resetting its status and re-dispatching."""
    run = get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Execution run not found")
    if run.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed runs can be retried")

    # Reset status and re-dispatch
    run.status = "queued"
    db.commit()
    db.refresh(run)

    # Dispatch based on run type
    if run.run_type in ("draft_section", "redraft_section"):
        section_key = run.input_json.get("section_key", "")
        review_feedback = run.input_json.get("review_feedback")
        kwargs = {"review_feedback": review_feedback} if review_feedback else {}
        celery.send_task("worker.draft_section", args=[run.id, run.project_id, section_key], kwargs=kwargs)
    elif run.run_type == "ingest_bundle":
        # For ingest, we need the bundle_id from input_json
        bundle_id = run.input_json.get("bundle_id", "")
        celery.send_task("worker.ingest_bundle", args=[bundle_id])

    record_audit_event(db, project_id=run.project_id, event_type="run.retried", payload={"run_id": run.id, "run_type": run.run_type})
    db.commit()

    return ExecutionRunRead(id=run.id, project_id=run.project_id, run_type=run.run_type, status=run.status, input_json=run.input_json, output_json=run.output_json)
