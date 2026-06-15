import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth.service import require_admin
from app.db import get_db
from app.billing.service import get_billing_summary
from app.models import ExecutionRun, User
from app.usage.service import list_usage_events_for_user

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/runtime-summary")
def runtime_summary(db: Session = Depends(get_db)) -> dict[str, object]:
    queued = db.scalar(
        select(func.count()).select_from(ExecutionRun).where(ExecutionRun.status == "queued")
    ) or 0
    failed = db.scalar(
        select(func.count()).select_from(ExecutionRun).where(ExecutionRun.status == "failed")
    ) or 0
    total = db.scalar(select(func.count()).select_from(ExecutionRun)) or 0
    succeeded = db.scalar(
        select(func.count()).select_from(ExecutionRun).where(ExecutionRun.status == "succeeded")
    ) or 0
    draft_success_rate = succeeded / total if total > 0 else 1.0
    return {
        "queue_depth": queued,
        "failed_runs": failed,
        "draft_success_rate": round(draft_success_rate, 2),
    }


@router.get("/health-detailed")
def health_detailed(db: Session = Depends(get_db)) -> dict[str, object]:
    """Detailed health check for all infrastructure dependencies."""
    checks: dict[str, object] = {}

    # Postgres
    try:
        db.scalar(text("SELECT 1"))
        checks["postgres"] = {"status": "ok"}
    except Exception as exc:
        checks["postgres"] = {"status": "error", "detail": str(exc)[:200]}

    # Redis
    try:
        import redis as redis_lib
        redis_url = os.environ.get("DOCPILOT_REDIS_URL", "redis://localhost:6379/0")
        r = redis_lib.from_url(redis_url)
        r.ping()
        checks["redis"] = {"status": "ok"}
    except Exception as exc:
        checks["redis"] = {"status": "error", "detail": str(exc)[:200]}

    # MinIO
    try:
        from app.adapters.storage import _get_client
        client = _get_client()
        # Just check we can connect
        client.list_buckets()
        checks["minio"] = {"status": "ok"}
    except Exception as exc:
        checks["minio"] = {"status": "error", "detail": str(exc)[:200]}

    # Celery Worker
    try:
        from celery import Celery
        redis_url = os.environ.get("DOCPILOT_REDIS_URL", "redis://localhost:6379/0")
        app = Celery("docpilot-check", broker=redis_url)
        insp = app.control.inspect()
        stats = insp.stats()
        if stats:
            checks["worker"] = {"status": "ok", "active_workers": len(stats)}
        else:
            checks["worker"] = {"status": "degraded", "detail": "No workers responding"}
    except Exception as exc:
        checks["worker"] = {"status": "error", "detail": str(exc)[:200]}

    all_ok = all(v.get("status") == "ok" for v in checks.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
    }


@router.get("/billing/users/{user_id}")
def billing_user_summary(
    user_id: str,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    summary = get_billing_summary(db, user_id)
    return {
        "data": {
            "user_id": user_id,
            "email": user.email,
            "display_name": user.display_name,
            **summary.model_dump(),
        }
    }


@router.get("/billing/usage/{user_id}")
def billing_user_usage(
    user_id: str,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"data": list_usage_events_for_user(db, user_id)}
