"""Resolve commercial capability from the active organization boundary."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Organization,
    OrganizationMembership,
    OrganizationSubscription,
    Subscription,
    User,
)

from .constants import (
    PLAN_PROJECT_LIMITS,
    STARTER_OFFICIAL_ASSISTANT_LIMIT,
    STARTER_OFFICIAL_INDEXING_LIMIT,
    STARTER_OFFICIAL_WORKFLOW_LIMIT,
    VALID_PLANS,
    VALID_SUBSCRIPTION_STATUSES,
    normalized_effective_plan,
    plan_limit,
)
from .schemas import OrganizationEntitlementRead


ACTIVE_MEMBERSHIP_STATUS = "active"
OWNER_ROLE = "owner"


class EntitlementAccessDenied(PermissionError):
    """Raised when an actor does not belong to the requested organization."""


class SeatCapacityExceeded(ValueError):
    """Raised before an active membership would exceed purchased capacity."""


@dataclass(frozen=True)
class EntitlementContext:
    org_id: str
    actor_user_id: str
    plan: str
    subscription_status: str
    source: str
    seat_limit: int
    active_member_count: int
    available_seats: int
    seat_overage_count: int
    capacity_enforced: bool
    project_limit: int
    monthly_workflow_limit: int
    monthly_assistant_limit: int
    monthly_indexing_limit: int
    stripe_customer_id: str | None
    is_billing_owner: bool

    def to_read(self) -> OrganizationEntitlementRead:
        return OrganizationEntitlementRead(
            org_id=self.org_id,
            plan=self.plan,
            subscription_status=self.subscription_status,
            source=self.source,  # type: ignore[arg-type]
            seat_limit=self.seat_limit,
            active_member_count=self.active_member_count,
            available_seats=self.available_seats,
            seat_overage_count=self.seat_overage_count,
            capacity_enforced=self.capacity_enforced,
            project_limit=self.project_limit,
            monthly_workflow_limit=self.monthly_workflow_limit,
            monthly_assistant_limit=self.monthly_assistant_limit,
            monthly_indexing_limit=self.monthly_indexing_limit,
            is_billing_owner=self.is_billing_owner,
        )


def _active_membership(db: Session, *, org_id: str, user_id: str) -> OrganizationMembership | None:
    return db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.org_id == org_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == ACTIVE_MEMBERSHIP_STATUS,
        )
    )


def _context(
    *,
    org_id: str,
    actor_user_id: str,
    plan: str,
    status: str,
    source: str,
    seat_limit: int,
    active_member_count: int,
    capacity_enforced: bool,
    stripe_customer_id: str | None,
    is_billing_owner: bool,
) -> EntitlementContext:
    effective_plan = normalized_effective_plan(plan, status)
    effective_seat_limit = _effective_seat_limit(plan, status, seat_limit)
    seat_overage_count = max(active_member_count - effective_seat_limit, 0)
    return EntitlementContext(
        org_id=org_id,
        actor_user_id=actor_user_id,
        plan=effective_plan,
        subscription_status=status,
        source=source,
        seat_limit=effective_seat_limit,
        active_member_count=active_member_count,
        available_seats=max(effective_seat_limit - active_member_count, 0),
        seat_overage_count=seat_overage_count,
        capacity_enforced=capacity_enforced,
        project_limit=PLAN_PROJECT_LIMITS[effective_plan],
        monthly_workflow_limit=plan_limit(
            effective_plan,
            STARTER_OFFICIAL_WORKFLOW_LIMIT,
        ),
        monthly_assistant_limit=plan_limit(
            effective_plan,
            STARTER_OFFICIAL_ASSISTANT_LIMIT,
        ),
        monthly_indexing_limit=plan_limit(
            effective_plan,
            STARTER_OFFICIAL_INDEXING_LIMIT,
        ),
        stripe_customer_id=stripe_customer_id,
        is_billing_owner=is_billing_owner,
    )


def _active_member_count(db: Session, org_id: str) -> int:
    return int(
        db.scalar(
            select(func.count()).select_from(OrganizationMembership).where(
                OrganizationMembership.org_id == org_id,
                OrganizationMembership.status == ACTIVE_MEMBERSHIP_STATUS,
            )
        )
        or 0
    )


def _effective_seat_limit(plan: str, status: str, configured_limit: int) -> int:
    """Do not retain purchased team capacity after a paid plan becomes inactive."""
    return configured_limit if normalized_effective_plan(plan, status) != "starter" else 1


def organization_seat_capacity(db: Session, org_id: str) -> tuple[int, int, bool]:
    """Return effective capacity, active-member count, and enforcement state.

    Existing organizations without a workspace subscription remain in migration
    compatibility mode. New workspaces create a starter OrganizationSubscription
    and therefore enforce their configured capacity.
    """
    active_member_count = _active_member_count(db, org_id)
    subscription = db.scalar(
        select(OrganizationSubscription).where(OrganizationSubscription.org_id == org_id)
    )
    if subscription is None:
        return 1, active_member_count, False
    return (
        _effective_seat_limit(subscription.plan, subscription.status, subscription.seat_limit),
        active_member_count,
        True,
    )


def ensure_organization_seat_available(db: Session, *, org_id: str) -> None:
    """Reject a new active member when a managed workspace is at capacity."""
    locked_org_id = db.scalar(
        select(Organization.id)
        .where(Organization.id == org_id)
        .with_for_update()
    )
    if locked_org_id is None:
        raise ValueError("Organization not found")
    seat_limit, active_member_count, capacity_enforced = organization_seat_capacity(db, org_id)
    if capacity_enforced and active_member_count >= seat_limit:
        raise SeatCapacityExceeded(
            "Organization seat capacity has been reached. Ask an owner to increase seats."
        )


def resolve_org_entitlements(
    db: Session,
    *,
    org_id: str,
    actor_user_id: str,
) -> EntitlementContext:
    """Return the only entitlement context valid for this organization request."""
    if db.get(Organization, org_id) is None:
        raise EntitlementAccessDenied("Organization access denied")

    membership = _active_membership(db, org_id=org_id, user_id=actor_user_id)
    if membership is None:
        raise EntitlementAccessDenied("Organization access denied")

    seat_limit, active_member_count, capacity_enforced = organization_seat_capacity(db, org_id)
    organization_subscription = db.scalar(
        select(OrganizationSubscription).where(OrganizationSubscription.org_id == org_id)
    )
    if organization_subscription is not None:
        return _context(
            org_id=org_id,
            actor_user_id=actor_user_id,
            plan=organization_subscription.plan,
            status=organization_subscription.status,
            source="organization",
            seat_limit=seat_limit,
            active_member_count=active_member_count,
            capacity_enforced=capacity_enforced,
            stripe_customer_id=organization_subscription.stripe_customer_id,
            is_billing_owner=(
                membership.role == OWNER_ROLE
                and organization_subscription.billing_owner_user_id == actor_user_id
            ),
        )

    # Compatibility bridge for existing named-user subscriptions. It may apply
    # only to the user's currently selected workspace, never all memberships.
    actor = db.get(User, actor_user_id)
    if actor is not None and actor.org_id == org_id:
        legacy_subscription = db.scalar(
            select(Subscription).where(Subscription.user_id == actor_user_id)
        )
        if legacy_subscription is not None:
            return _context(
                org_id=org_id,
                actor_user_id=actor_user_id,
                plan=legacy_subscription.plan,
                status=legacy_subscription.status,
                source="legacy",
                seat_limit=seat_limit,
                active_member_count=active_member_count,
                capacity_enforced=capacity_enforced,
                stripe_customer_id=legacy_subscription.stripe_customer_id,
                is_billing_owner=membership.role == OWNER_ROLE,
            )

    return _context(
        org_id=org_id,
        actor_user_id=actor_user_id,
        plan="starter",
        status="active",
        source="starter",
        seat_limit=seat_limit,
        active_member_count=active_member_count,
        capacity_enforced=capacity_enforced,
        stripe_customer_id=None,
        is_billing_owner=membership.role == OWNER_ROLE,
    )


def upsert_organization_subscription_command(
    db: Session,
    *,
    org_id: str,
    billing_owner_user_id: str,
    plan: str,
    status: str = "active",
    seat_limit: int = 1,
    billable_seat_count: int | None = None,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
    stripe_subscription_item_id: str | None = None,
    stripe_state_event_created_at: int | None = None,
    commit: bool = True,
) -> OrganizationSubscription:
    """Create or update a workspace subscription after validating its owner."""
    if plan not in VALID_PLANS:
        raise ValueError(f"Invalid plan: {plan}")
    if status not in VALID_SUBSCRIPTION_STATUSES:
        raise ValueError(f"Invalid subscription status: {status}")
    if seat_limit < 1:
        raise ValueError("seat_limit must be at least 1")
    if db.get(Organization, org_id) is None:
        raise ValueError("Organization not found")
    owner_membership = _active_membership(
        db,
        org_id=org_id,
        user_id=billing_owner_user_id,
    )
    if owner_membership is None or owner_membership.role != OWNER_ROLE:
        raise ValueError("Billing owner must be an active organization owner")

    subscription = db.scalar(
        select(OrganizationSubscription).where(OrganizationSubscription.org_id == org_id)
    )
    if subscription is None:
        subscription = OrganizationSubscription(
            org_id=org_id,
            billing_owner_user_id=billing_owner_user_id,
            plan=plan,
            status=status,
            seat_limit=seat_limit,
            billable_seat_count=(
                billable_seat_count if billable_seat_count is not None else seat_limit
            ),
        )
        db.add(subscription)
    else:
        subscription.billing_owner_user_id = billing_owner_user_id
        subscription.plan = plan
        subscription.status = status
        subscription.seat_limit = seat_limit
        if billable_seat_count is not None:
            subscription.billable_seat_count = billable_seat_count

    if subscription.billable_seat_count < 0:
        raise ValueError("billable_seat_count cannot be negative")
    if stripe_customer_id is not None:
        subscription.stripe_customer_id = stripe_customer_id
    if stripe_subscription_id is not None:
        subscription.stripe_subscription_id = stripe_subscription_id
    if stripe_subscription_item_id is not None:
        subscription.stripe_subscription_item_id = stripe_subscription_item_id
    if stripe_state_event_created_at is not None:
        subscription.stripe_state_event_created_at = stripe_state_event_created_at

    if commit:
        db.commit()
        db.refresh(subscription)
    else:
        db.flush()
    return subscription
