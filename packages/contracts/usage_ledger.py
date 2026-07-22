"""Durable model-usage ledger and optional token-budget reservations.

This module is deliberately shared by the API and Worker. It contains no
request/auth logic: callers must authorize the organization before invoking it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .model_usage import ProviderUsageMeasurement
from .models import Organization, ModelUsageRecord, ModelUsageReservation, OrganizationUsageBudget


ProviderUsageSource = Literal["official", "byok"]
ReservationStatus = Literal[
    "reserved",
    "dispatched",
    "settled",
    "released",
    "uncertain",
    "expired",
]

ACTIVE_RESERVATION_STATUSES = ("reserved", "dispatched", "uncertain")
DEFAULT_RESERVATION_TTL = timedelta(minutes=30)


class ModelUsageBudgetExceeded(ValueError):
    """Raised before dispatch when an organization token cap would be exceeded."""


@dataclass(frozen=True)
class ModelUsageSourceSummary:
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    total_tokens: int
    reserved_tokens: int
    token_limit: int | None
    remaining_tokens: int | None


def current_period_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _token_limit(budget: OrganizationUsageBudget | None, source: ProviderUsageSource) -> int | None:
    if budget is None:
        return None
    return budget.official_monthly_token_limit if source == "official" else budget.byok_monthly_token_limit


def effective_token_limit(*limits: int | None) -> int | None:
    """Return the strictest configured token limit without treating ``None`` as zero."""
    configured = [limit for limit in limits if limit is not None]
    if any(limit < 0 for limit in configured):
        raise ValueError("token limits must be non-negative")
    return min(configured) if configured else None


def _expire_stale_reservations(db: Session, *, org_id: str, now: datetime) -> None:
    stale = list(
        db.scalars(
            select(ModelUsageReservation).where(
                ModelUsageReservation.org_id == org_id,
                ModelUsageReservation.status.in_(ACTIVE_RESERVATION_STATUSES),
                ModelUsageReservation.expires_at <= now,
            )
        )
    )
    for reservation in stale:
        reservation.status = "expired"
        reservation.settled_at = now
    if stale:
        db.flush()


def _recorded_total_tokens(
    db: Session,
    *,
    org_id: str,
    provider_source: ProviderUsageSource,
    start: datetime,
    end: datetime,
) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(ModelUsageRecord.total_tokens), 0)).where(
                ModelUsageRecord.org_id == org_id,
                ModelUsageRecord.provider_source == provider_source,
                ModelUsageRecord.created_at >= start,
                ModelUsageRecord.created_at < end,
            )
        )
        or 0
    )


def _reserved_total_tokens(
    db: Session,
    *,
    org_id: str,
    provider_source: ProviderUsageSource,
    now: datetime,
) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(ModelUsageReservation.reserved_tokens), 0)).where(
                ModelUsageReservation.org_id == org_id,
                ModelUsageReservation.provider_source == provider_source,
                ModelUsageReservation.status.in_(ACTIVE_RESERVATION_STATUSES),
                ModelUsageReservation.expires_at > now,
            )
        )
        or 0
    )


def reserve_model_tokens(
    db: Session,
    *,
    org_id: str,
    user_id: str | None,
    provider_source: ProviderUsageSource,
    workload: str,
    reservation_key: str,
    reserved_tokens: int,
    project_id: str | None = None,
    execution_run_id: str | None = None,
    runtime_run_id: str | None = None,
    now: datetime | None = None,
    ttl: timedelta = DEFAULT_RESERVATION_TTL,
    token_limit_ceiling: int | None = None,
) -> ModelUsageReservation | None:
    """Reserve conservative token capacity before dispatching a model call.

    There is intentionally no row when neither the workspace nor the platform
    has a token cap. Existing request-count quotas remain enforced by the API
    service.
    """
    if reserved_tokens <= 0:
        raise ValueError("reserved_tokens must be positive")
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    # Lock the durable organization row even when no optional budget row exists.
    # A platform ceiling must not be bypassed by two concurrent first requests.
    organization_id = db.scalar(
        select(Organization.id).where(Organization.id == org_id).with_for_update()
    )
    if organization_id is None:
        raise ValueError("Organization not found")

    budget = db.scalar(
        select(OrganizationUsageBudget)
        .where(OrganizationUsageBudget.org_id == org_id)
        .with_for_update()
    )
    limit = effective_token_limit(_token_limit(budget, provider_source), token_limit_ceiling)
    if limit is None:
        return None

    existing = db.scalar(
        select(ModelUsageReservation)
        .where(
            ModelUsageReservation.org_id == org_id,
            ModelUsageReservation.reservation_key == reservation_key,
        )
        .with_for_update()
    )
    if existing is not None:
        return existing

    _expire_stale_reservations(db, org_id=org_id, now=current)
    start, end = current_period_bounds(current)
    used = _recorded_total_tokens(
        db,
        org_id=org_id,
        provider_source=provider_source,
        start=start,
        end=end,
    )
    held = _reserved_total_tokens(
        db,
        org_id=org_id,
        provider_source=provider_source,
        now=current,
    )
    if used + held + reserved_tokens > limit:
        raise ModelUsageBudgetExceeded(
            "The configured organization AI token budget has been reached."
        )

    reservation = ModelUsageReservation(
        org_id=org_id,
        user_id=user_id,
        project_id=project_id,
        execution_run_id=execution_run_id,
        runtime_run_id=runtime_run_id,
        provider_source=provider_source,
        workload=workload,
        reservation_key=reservation_key,
        reserved_tokens=reserved_tokens,
        status="reserved",
        expires_at=current + ttl,
    )
    db.add(reservation)
    db.flush()
    return reservation


def attach_model_reservation(
    db: Session,
    reservation: ModelUsageReservation | None,
    *,
    execution_run_id: str | None = None,
    runtime_run_id: str | None = None,
) -> None:
    """Attach a preflight reservation after durable run IDs are created."""
    if reservation is None:
        return
    if execution_run_id is not None:
        reservation.execution_run_id = execution_run_id
    if runtime_run_id is not None:
        reservation.runtime_run_id = runtime_run_id
    db.flush()


def record_model_usage(
    db: Session,
    *,
    org_id: str,
    user_id: str | None,
    provider_source: ProviderUsageSource,
    provider_type: str,
    model_name: str,
    workload: str,
    measurement: ProviderUsageMeasurement,
    project_id: str | None = None,
    execution_run_id: str | None = None,
    runtime_run_id: str | None = None,
    provider_config_id: str | None = None,
) -> ModelUsageRecord:
    """Append one provider-reported measurement without raw response content."""
    record = ModelUsageRecord(
        org_id=org_id,
        user_id=user_id,
        project_id=project_id,
        execution_run_id=execution_run_id,
        runtime_run_id=runtime_run_id,
        provider_source=provider_source,
        provider_type=provider_type,
        provider_config_id=provider_config_id,
        model_name=model_name,
        workload=workload,
        input_tokens=measurement.input_tokens,
        output_tokens=measurement.output_tokens,
        reasoning_tokens=measurement.reasoning_tokens,
        cache_read_tokens=measurement.cache_read_tokens,
        cache_write_tokens=measurement.cache_write_tokens,
        total_tokens=measurement.total_tokens,
        measurement_source="provider_reported",
    )
    db.add(record)
    db.flush()
    return record


def _find_reservation(
    db: Session,
    *,
    org_id: str,
    reservation_key: str,
) -> ModelUsageReservation | None:
    return db.scalar(
        select(ModelUsageReservation)
        .where(
            ModelUsageReservation.org_id == org_id,
            ModelUsageReservation.reservation_key == reservation_key,
        )
        .with_for_update()
    )


def settle_model_reservation(
    db: Session,
    *,
    org_id: str,
    reservation_key: str,
    now: datetime | None = None,
) -> None:
    reservation = _find_reservation(db, org_id=org_id, reservation_key=reservation_key)
    if reservation is None or reservation.status not in ACTIVE_RESERVATION_STATUSES:
        return
    reservation.status = "settled"
    reservation.settled_at = now or datetime.now(UTC)
    db.flush()


def release_model_reservation(
    db: Session,
    *,
    org_id: str,
    reservation_key: str,
    now: datetime | None = None,
) -> None:
    reservation = _find_reservation(db, org_id=org_id, reservation_key=reservation_key)
    if reservation is None or reservation.status not in ACTIVE_RESERVATION_STATUSES:
        return
    reservation.status = "released"
    reservation.settled_at = now or datetime.now(UTC)
    db.flush()


def mark_model_reservation_uncertain(
    db: Session,
    *,
    org_id: str,
    reservation_key: str,
) -> None:
    """Keep capacity reserved when a provider may have charged an unseen call."""
    reservation = _find_reservation(db, org_id=org_id, reservation_key=reservation_key)
    if reservation is None or reservation.status not in {"reserved", "dispatched"}:
        return
    reservation.status = "uncertain"
    db.flush()


def model_usage_summary(
    db: Session,
    *,
    org_id: str,
    provider_source: ProviderUsageSource,
    now: datetime | None = None,
    token_limit_ceiling: int | None = None,
) -> ModelUsageSourceSummary:
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    _expire_stale_reservations(db, org_id=org_id, now=current)
    start, end = current_period_bounds(current)
    aggregates = db.execute(
        select(
            func.coalesce(func.sum(ModelUsageRecord.input_tokens), 0),
            func.coalesce(func.sum(ModelUsageRecord.output_tokens), 0),
            func.coalesce(func.sum(ModelUsageRecord.reasoning_tokens), 0),
            func.coalesce(func.sum(ModelUsageRecord.cache_read_tokens), 0),
            func.coalesce(func.sum(ModelUsageRecord.cache_write_tokens), 0),
            func.coalesce(func.sum(ModelUsageRecord.total_tokens), 0),
        ).where(
            ModelUsageRecord.org_id == org_id,
            ModelUsageRecord.provider_source == provider_source,
            ModelUsageRecord.created_at >= start,
            ModelUsageRecord.created_at < end,
        )
    ).one()
    budget = db.scalar(
        select(OrganizationUsageBudget).where(OrganizationUsageBudget.org_id == org_id)
    )
    limit = effective_token_limit(_token_limit(budget, provider_source), token_limit_ceiling)
    total = int(aggregates[5] or 0)
    reserved = _reserved_total_tokens(
        db,
        org_id=org_id,
        provider_source=provider_source,
        now=current,
    )
    return ModelUsageSourceSummary(
        input_tokens=int(aggregates[0] or 0),
        output_tokens=int(aggregates[1] or 0),
        reasoning_tokens=int(aggregates[2] or 0),
        cache_read_tokens=int(aggregates[3] or 0),
        cache_write_tokens=int(aggregates[4] or 0),
        total_tokens=total,
        reserved_tokens=reserved,
        token_limit=limit,
        remaining_tokens=None if limit is None else max(limit - total - reserved, 0),
    )
