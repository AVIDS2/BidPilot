from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Subscription, UsageEvent

from .schemas import ProviderSource, UsageQuotaRead


STARTER_OFFICIAL_WORKFLOW_LIMIT = 3
WORKFLOW_DRAFT_STARTED = "workflow_draft_started"


class UsageLimitExceeded(ValueError):
    """Raised when a user exceeds a server-side usage limit."""


def get_user_plan(db: Session, user_id: str) -> str:
    sub = db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    return sub.plan if sub else "starter"


def _month_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = now or datetime.now(UTC)
    start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def current_period_key(now: datetime | None = None) -> str:
    current = now or datetime.now(UTC)
    return current.strftime("%Y-%m")


def count_official_workflow_starts(db: Session, user_id: str, now: datetime | None = None) -> int:
    period_key = current_period_key(now)
    stmt = select(func.coalesce(func.sum(UsageEvent.units), 0)).where(
        UsageEvent.user_id == user_id,
        UsageEvent.event_type == WORKFLOW_DRAFT_STARTED,
        UsageEvent.provider_source == ProviderSource.OFFICIAL.value,
        UsageEvent.period_key == period_key,
    )
    return int(db.scalar(stmt) or 0)


def get_usage_quota(db: Session, user_id: str) -> UsageQuotaRead:
    now = datetime.now(UTC)
    month_start, _ = _month_bounds(now)
    plan = get_user_plan(db, user_id)
    used = count_official_workflow_starts(db, user_id, now)
    limit = STARTER_OFFICIAL_WORKFLOW_LIMIT if plan not in {"professional", "enterprise"} else -1
    remaining = None if limit < 0 else max(limit - used, 0)
    return UsageQuotaRead(
        plan=plan,
        monthly_workflow_limit=limit,
        monthly_workflow_used=used,
        monthly_workflow_remaining=remaining,
        trial_window_start=month_start.isoformat(),
    )


def usage_quota_dict(db: Session, user_id: str) -> dict:
    quota = get_usage_quota(db, user_id)
    return quota.model_dump()


def list_usage_events_for_user(db: Session, user_id: str) -> list[dict[str, object]]:
    events = list(
        db.query(UsageEvent)
        .filter(UsageEvent.user_id == user_id)
        .order_by(UsageEvent.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": event.id,
            "user_id": event.user_id,
            "org_id": event.org_id,
            "project_id": event.project_id,
            "event_type": event.event_type,
            "provider_source": event.provider_source,
            "units": event.units,
            "period_key": event.period_key,
            "execution_run_id": event.execution_run_id,
            "metadata_json": event.metadata_json,
            "created_at": event.created_at.isoformat() if event.created_at else "",
        }
        for event in events
    ]


def check_workflow_quota(
    db: Session,
    user_id: str,
    org_id: str,
    provider_source: ProviderSource,
) -> None:
    if provider_source != ProviderSource.OFFICIAL:
        return
    plan = get_user_plan(db, user_id)
    if plan in {"professional", "enterprise"}:
        return
    used = count_official_workflow_starts(db, user_id)
    if used >= STARTER_OFFICIAL_WORKFLOW_LIMIT:
        raise UsageLimitExceeded(
            f"starter workflow trial limit of {STARTER_OFFICIAL_WORKFLOW_LIMIT} official runs has been reached"
        )


def record_usage_event(
    db: Session,
    *,
    user_id: str,
    org_id: str,
    event_type: str,
    provider_source: ProviderSource,
    project_id: str | None = None,
    execution_run_id: str | None = None,
    units: int = 1,
    metadata_json: dict | None = None,
) -> UsageEvent:
    event = UsageEvent(
        user_id=user_id,
        org_id=org_id,
        project_id=project_id,
        event_type=event_type,
        provider_source=provider_source.value,
        execution_run_id=execution_run_id,
        units=units,
        period_key=current_period_key(),
        metadata_json=metadata_json,
    )
    db.add(event)
    db.flush()
    return event
