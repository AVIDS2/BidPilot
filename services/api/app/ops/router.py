from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.service import require_admin
from app.db import get_db
from app.billing.service import get_billing_summary, list_stripe_webhook_receipts
from app.models import ExecutionRun, User
from app.ops.health import collect_dependency_checks, dependencies_are_ready
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
    """Detailed health without returning backend errors or connection data."""
    check_states = collect_dependency_checks(db, include_worker=True)
    checks = {name: {"status": state} for name, state in check_states.items()}
    return {
        "status": "ok" if dependencies_are_ready(check_states) else "degraded",
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


@router.get("/billing/users/{user_id}/webhooks")
def billing_user_webhooks(
    user_id: str,
    limit: int = 100,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Show safe Stripe receipt outcomes for a customer support investigation."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"data": list_stripe_webhook_receipts(db, user_id=user_id, limit=limit)}
