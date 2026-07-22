from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contracts.usage_ledger import (
    ModelUsageBudgetExceeded,
    ModelUsageReservation,
    attach_model_reservation,
    effective_token_limit,
    model_usage_summary,
    reserve_model_tokens,
)
from contracts.usage_budget_policy import (
    OfficialTokenCeilingConfigurationError,
    configured_official_monthly_token_ceiling,
    require_official_monthly_token_ceiling,
)

from app.entitlements.constants import (
    STARTER_OFFICIAL_ASSISTANT_LIMIT,
    STARTER_OFFICIAL_INDEXING_LIMIT,
    STARTER_OFFICIAL_WORKFLOW_LIMIT,
)
from app.entitlements.service import EntitlementAccessDenied, resolve_org_entitlements
from app.models import Organization, OrganizationUsageBudget, OrganizationUsageBudgetEvent, UsageEvent, User
from app.runtime.model_limits import OPERATOR_PLANNER_RESERVATION_TOKENS

from .schemas import (
    ModelUsageSourceRead,
    OrganizationUsageBudgetRead,
    ProviderSource,
    UsageQuotaRead,
)


WORKFLOW_DRAFT_STARTED = "workflow_draft_started"
ASSISTANT_MESSAGE_STARTED = "assistant_message_started"
EMBEDDING_INDEX_STARTED = "embedding_index_started"

# Conservative per-call bounds used by the platform ceiling and any stricter
# organization budget. Worker adapters bound the drafting prompt and output;
# the Operator reserves independently before each planner invocation.
WORKFLOW_OPENAI_RESERVED_TOKENS = 16_000
WORKFLOW_ANTHROPIC_RESERVED_TOKENS = 32_000
ASSISTANT_PLANNER_RESERVED_TOKENS = OPERATOR_PLANNER_RESERVATION_TOKENS


class UsageLimitExceeded(ValueError):
    """Raised when a workspace exceeds a server-side usage limit."""


def _official_token_ceiling(*, require_configured: bool) -> int | None:
    """Resolve platform-funded capacity without applying it to a user's BYOK calls."""
    try:
        if require_configured:
            return require_official_monthly_token_ceiling()
        return configured_official_monthly_token_ceiling()
    except OfficialTokenCeilingConfigurationError as exc:
        raise UsageLimitExceeded("平台模型额度保护尚未正确配置，暂不能使用平台模型。") from exc


def _model_usage_read(summary) -> ModelUsageSourceRead:
    return ModelUsageSourceRead(
        input_tokens=summary.input_tokens,
        output_tokens=summary.output_tokens,
        reasoning_tokens=summary.reasoning_tokens,
        cache_read_tokens=summary.cache_read_tokens,
        cache_write_tokens=summary.cache_write_tokens,
        total_tokens=summary.total_tokens,
        reserved_tokens=summary.reserved_tokens,
        token_limit=summary.token_limit,
        remaining_tokens=summary.remaining_tokens,
    )


def _resolve_scope(
    db: Session,
    *,
    user_id: str | None = None,
    org_id: str | None = None,
    actor_user_id: str | None = None,
) -> tuple[str, str]:
    """Resolve a request scope while preserving only internal legacy callers."""
    if org_id is None:
        if user_id is None:
            raise ValueError("org_id and actor_user_id are required")
        user = db.get(User, user_id)
        if user is None:
            raise ValueError("User not found")
        org_id = user.org_id
        actor_user_id = user.id
    elif actor_user_id is None:
        actor_user_id = user_id

    if not actor_user_id:
        raise ValueError("actor_user_id is required")
    return org_id, actor_user_id


def get_user_plan(db: Session, user_id: str) -> str:
    """Compatibility read for callers that only know a user's active workspace."""
    user = db.get(User, user_id)
    if user is None:
        return "starter"
    try:
        return resolve_org_entitlements(
            db,
            org_id=user.org_id,
            actor_user_id=user.id,
        ).plan
    except EntitlementAccessDenied:
        # Missing membership is never allowed to retain a paid entitlement.
        return "starter"


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


def _sum_usage_units(
    db: Session,
    org_id: str,
    *,
    event_type: str,
    provider_source: ProviderSource,
    now: datetime | None = None,
) -> int:
    period_key = current_period_key(now)
    stmt = select(func.coalesce(func.sum(UsageEvent.units), 0)).where(
        UsageEvent.org_id == org_id,
        UsageEvent.event_type == event_type,
        UsageEvent.provider_source == provider_source.value,
        UsageEvent.period_key == period_key,
    )
    return int(db.scalar(stmt) or 0)


def _remaining(limit: int, used: int) -> int | None:
    return None if limit < 0 else max(limit - used, 0)


def count_official_workflow_starts(
    db: Session,
    org_id: str,
    now: datetime | None = None,
) -> int:
    return _sum_usage_units(
        db,
        org_id,
        event_type=WORKFLOW_DRAFT_STARTED,
        provider_source=ProviderSource.OFFICIAL,
        now=now,
    )


def count_official_assistant_messages(
    db: Session,
    org_id: str,
    now: datetime | None = None,
) -> int:
    return _sum_usage_units(
        db,
        org_id,
        event_type=ASSISTANT_MESSAGE_STARTED,
        provider_source=ProviderSource.OFFICIAL,
        now=now,
    )


def count_official_indexing_starts(
    db: Session,
    org_id: str,
    now: datetime | None = None,
) -> int:
    return _sum_usage_units(
        db,
        org_id,
        event_type=EMBEDDING_INDEX_STARTED,
        provider_source=ProviderSource.OFFICIAL,
        now=now,
    )


def get_usage_quota(
    db: Session,
    user_id: str | None = None,
    *,
    org_id: str | None = None,
    actor_user_id: str | None = None,
) -> UsageQuotaRead:
    """Read official-provider quotas for the active organization workspace."""
    org_id, actor_user_id = _resolve_scope(
        db,
        user_id=user_id,
        org_id=org_id,
        actor_user_id=actor_user_id,
    )
    try:
        entitlement = resolve_org_entitlements(
            db,
            org_id=org_id,
            actor_user_id=actor_user_id,
        )
    except EntitlementAccessDenied as exc:
        raise UsageLimitExceeded("Active organization membership is required") from exc

    now = datetime.now(UTC)
    official_token_ceiling = _official_token_ceiling(require_configured=False)
    month_start, _ = _month_bounds(now)
    workflow_used = count_official_workflow_starts(db, org_id, now)
    assistant_used = count_official_assistant_messages(db, org_id, now)
    indexing_used = count_official_indexing_starts(db, org_id, now)
    return UsageQuotaRead(
        plan=entitlement.plan,
        monthly_workflow_limit=entitlement.monthly_workflow_limit,
        monthly_workflow_used=workflow_used,
        monthly_workflow_remaining=_remaining(
            entitlement.monthly_workflow_limit,
            workflow_used,
        ),
        monthly_assistant_limit=entitlement.monthly_assistant_limit,
        monthly_assistant_used=assistant_used,
        monthly_assistant_remaining=_remaining(
            entitlement.monthly_assistant_limit,
            assistant_used,
        ),
        monthly_indexing_limit=entitlement.monthly_indexing_limit,
        monthly_indexing_used=indexing_used,
        monthly_indexing_remaining=_remaining(
            entitlement.monthly_indexing_limit,
            indexing_used,
        ),
        official_model_usage=_model_usage_read(
            model_usage_summary(
                db,
                org_id=org_id,
                provider_source="official",
                now=now,
                token_limit_ceiling=official_token_ceiling,
            )
        ),
        byok_model_usage=_model_usage_read(
            model_usage_summary(db, org_id=org_id, provider_source="byok", now=now)
        ),
        trial_window_start=month_start.isoformat(),
    )


def usage_quota_dict(
    db: Session,
    user_id: str | None = None,
    *,
    org_id: str | None = None,
    actor_user_id: str | None = None,
) -> dict:
    quota = get_usage_quota(
        db,
        user_id,
        org_id=org_id,
        actor_user_id=actor_user_id,
    )
    return quota.model_dump()


def read_organization_usage_budget(
    db: Session,
    *,
    org_id: str,
    actor_user_id: str,
) -> OrganizationUsageBudgetRead:
    entitlement = resolve_org_entitlements(
        db,
        org_id=org_id,
        actor_user_id=actor_user_id,
    )
    budget = db.query(OrganizationUsageBudget).filter_by(org_id=org_id).one_or_none()
    configured_official_limit = (
        budget.official_monthly_token_limit if budget is not None else None
    )
    official_token_ceiling = _official_token_ceiling(require_configured=False)
    return OrganizationUsageBudgetRead(
        official_monthly_token_limit=configured_official_limit,
        byok_monthly_token_limit=(budget.byok_monthly_token_limit if budget is not None else None),
        official_platform_monthly_token_ceiling=official_token_ceiling,
        effective_official_monthly_token_limit=effective_token_limit(
            configured_official_limit,
            official_token_ceiling,
        ),
        can_manage=entitlement.is_billing_owner,
    )


def update_organization_usage_budget(
    db: Session,
    *,
    org_id: str,
    actor_user_id: str,
    updates: dict[str, int | None],
) -> OrganizationUsageBudgetRead:
    """Update optional token caps through the workspace billing owner only."""
    entitlement = resolve_org_entitlements(
        db,
        org_id=org_id,
        actor_user_id=actor_user_id,
    )
    if not entitlement.is_billing_owner:
        raise PermissionError("Only the workspace billing owner can change AI usage safeguards")
    # Serialize owner changes with model-reservation creation, including the
    # common case where this is the first custom budget row for an organization.
    organization_id = db.scalar(
        select(Organization.id).where(Organization.id == org_id).with_for_update()
    )
    if organization_id is None:
        raise ValueError("Organization not found")
    allowed_fields = {"official_monthly_token_limit", "byok_monthly_token_limit"}
    if not set(updates).issubset(allowed_fields):
        raise ValueError("Unsupported usage budget field")
    for value in updates.values():
        if value is not None and value < 0:
            raise ValueError("Usage budget values must be non-negative")

    official_token_ceiling = _official_token_ceiling(require_configured=True)
    requested_official_limit = updates.get("official_monthly_token_limit")
    if (
        requested_official_limit is not None
        and official_token_ceiling is not None
        and requested_official_limit > official_token_ceiling
    ):
        raise ValueError("Official token budget cannot exceed the platform safety ceiling")

    if not updates:
        return read_organization_usage_budget(
            db,
            org_id=org_id,
            actor_user_id=actor_user_id,
        )

    budget = db.query(OrganizationUsageBudget).filter_by(org_id=org_id).one_or_none()
    previous_limits = {
        "official_monthly_token_limit": (
            budget.official_monthly_token_limit if budget is not None else None
        ),
        "byok_monthly_token_limit": budget.byok_monthly_token_limit if budget is not None else None,
    }
    updated_limits = {**previous_limits, **updates}
    if updated_limits == previous_limits:
        return OrganizationUsageBudgetRead(
            official_monthly_token_limit=previous_limits["official_monthly_token_limit"],
            byok_monthly_token_limit=previous_limits["byok_monthly_token_limit"],
            official_platform_monthly_token_ceiling=official_token_ceiling,
            effective_official_monthly_token_limit=effective_token_limit(
                previous_limits["official_monthly_token_limit"],
                official_token_ceiling,
            ),
            can_manage=True,
        )
    if budget is None:
        budget = OrganizationUsageBudget(org_id=org_id)
        db.add(budget)
    for field, value in updates.items():
        setattr(budget, field, value)
    db.add(
        OrganizationUsageBudgetEvent(
            org_id=org_id,
            actor_user_id=actor_user_id,
            event_type="usage_budget.updated",
            previous_limits_json=previous_limits,
            updated_limits_json=updated_limits,
        )
    )
    db.commit()
    return OrganizationUsageBudgetRead(
        official_monthly_token_limit=budget.official_monthly_token_limit,
        byok_monthly_token_limit=budget.byok_monthly_token_limit,
        official_platform_monthly_token_ceiling=official_token_ceiling,
        effective_official_monthly_token_limit=effective_token_limit(
            budget.official_monthly_token_limit,
            official_token_ceiling,
        ),
        can_manage=True,
    )


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


def _require_official_entitlement(
    db: Session,
    *,
    user_id: str,
    org_id: str,
):
    try:
        return resolve_org_entitlements(
            db,
            org_id=org_id,
            actor_user_id=user_id,
        )
    except EntitlementAccessDenied as exc:
        raise UsageLimitExceeded("Active organization membership is required") from exc


def check_workflow_quota(
    db: Session,
    user_id: str,
    org_id: str,
    provider_source: ProviderSource,
) -> None:
    if provider_source != ProviderSource.OFFICIAL:
        return
    entitlement = _require_official_entitlement(db, user_id=user_id, org_id=org_id)
    if entitlement.monthly_workflow_limit < 0:
        return
    used = count_official_workflow_starts(db, org_id)
    if used >= entitlement.monthly_workflow_limit:
        raise UsageLimitExceeded(
            "starter workflow trial limit of "
            f"{STARTER_OFFICIAL_WORKFLOW_LIMIT} official runs has been reached"
        )


def check_assistant_quota(
    db: Session,
    user_id: str,
    org_id: str,
    provider_source: ProviderSource,
) -> None:
    if provider_source != ProviderSource.OFFICIAL:
        return
    entitlement = _require_official_entitlement(db, user_id=user_id, org_id=org_id)
    if entitlement.monthly_assistant_limit < 0:
        return
    used = count_official_assistant_messages(db, org_id)
    if used >= entitlement.monthly_assistant_limit:
        raise UsageLimitExceeded(
            "starter assistant limit of "
            f"{STARTER_OFFICIAL_ASSISTANT_LIMIT} official messages has been reached"
        )


def check_indexing_quota(
    db: Session,
    user_id: str,
    org_id: str,
    provider_source: ProviderSource,
) -> None:
    if provider_source != ProviderSource.OFFICIAL:
        return
    entitlement = _require_official_entitlement(db, user_id=user_id, org_id=org_id)
    if entitlement.monthly_indexing_limit < 0:
        return
    used = count_official_indexing_starts(db, org_id)
    if used >= entitlement.monthly_indexing_limit:
        raise UsageLimitExceeded(
            "starter indexing limit of "
            f"{STARTER_OFFICIAL_INDEXING_LIMIT} official indexing jobs has been reached"
        )


def reserve_workflow_model_tokens(
    db: Session,
    *,
    user_id: str,
    org_id: str,
    provider_source: ProviderSource,
    provider_type: str,
    reservation_key: str,
    project_id: str,
    execution_run_id: str | None = None,
    runtime_run_id: str | None = None,
) -> ModelUsageReservation | None:
    """Reserve server-owned model capacity before a drafting job is queued."""
    if provider_source == ProviderSource.STUB:
        return None
    reserved_tokens = (
        WORKFLOW_ANTHROPIC_RESERVED_TOKENS
        if provider_type == "anthropic"
        else WORKFLOW_OPENAI_RESERVED_TOKENS
    )
    try:
        token_limit_ceiling = (
            _official_token_ceiling(require_configured=True)
            if provider_source == ProviderSource.OFFICIAL
            else None
        )
        return reserve_model_tokens(
            db,
            org_id=org_id,
            user_id=user_id,
            provider_source=provider_source.value,  # type: ignore[arg-type]
            # This is a generic workflow-start hold. The Worker attributes
            # each real provider response to its semantic workload later.
            workload="workflow_execution",
            reservation_key=reservation_key,
            reserved_tokens=reserved_tokens,
            project_id=project_id,
            execution_run_id=execution_run_id,
            runtime_run_id=runtime_run_id,
            token_limit_ceiling=token_limit_ceiling,
        )
    except ModelUsageBudgetExceeded as exc:
        raise UsageLimitExceeded("工作区本月 AI token 预算已用尽，请联系工作区管理员。") from exc


def reserve_assistant_model_tokens(
    db: Session,
    *,
    user_id: str,
    org_id: str,
    provider_source: ProviderSource,
    reservation_key: str,
    project_id: str | None,
    runtime_run_id: str,
) -> ModelUsageReservation | None:
    """Reserve bounded Operator-planning capacity for one graph invocation."""
    if provider_source == ProviderSource.STUB:
        return None
    try:
        token_limit_ceiling = (
            _official_token_ceiling(require_configured=True)
            if provider_source == ProviderSource.OFFICIAL
            else None
        )
        return reserve_model_tokens(
            db,
            org_id=org_id,
            user_id=user_id,
            provider_source=provider_source.value,  # type: ignore[arg-type]
            workload="assistant_planning",
            reservation_key=reservation_key,
            reserved_tokens=ASSISTANT_PLANNER_RESERVED_TOKENS,
            project_id=project_id,
            runtime_run_id=runtime_run_id,
            token_limit_ceiling=token_limit_ceiling,
        )
    except ModelUsageBudgetExceeded as exc:
        raise UsageLimitExceeded("工作区本月 AI token 预算已用尽，请联系工作区管理员。") from exc


def attach_model_usage_reservation(
    db: Session,
    reservation: ModelUsageReservation | None,
    *,
    execution_run_id: str | None = None,
    runtime_run_id: str | None = None,
) -> None:
    """Link a preflight reservation after durable run IDs are available."""
    attach_model_reservation(
        db,
        reservation,
        execution_run_id=execution_run_id,
        runtime_run_id=runtime_run_id,
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
