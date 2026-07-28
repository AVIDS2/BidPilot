from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.stripe_adapter import PLAN_PRICE_IDS
from app.auth.service import VALID_PLANS, VALID_SUBSCRIPTION_STATUSES, update_subscription_command
from app.entitlements.service import (
    ACTIVE_MEMBERSHIP_STATUS,
    OWNER_ROLE,
    resolve_org_entitlements,
    upsert_organization_subscription_command,
)
from app.models import (
    OrganizationMembership,
    OrganizationSubscription,
    StripeWebhookEvent,
    Subscription,
    User,
)
from app.usage.service import get_usage_quota

from .schemas import BillingSummaryRead


@dataclass(frozen=True)
class StripeWebhookProcessResult:
    """Safe, user-neutral result of handling a signed Stripe event."""

    outcome: str
    duplicate: bool = False


@dataclass(frozen=True)
class _BillingTarget:
    """One local billing record resolved before a Stripe event is applied."""

    scope: str
    user_id: str | None
    org_id: str | None
    subscription: Subscription | OrganizationSubscription | None
    stripe_customer_id: str | None
    stripe_subscription_id: str | None


_SUBSCRIPTION_EVENTS = {
    "customer.subscription.created",
    "customer.subscription.updated",
}
_SUPPORTED_EVENT_TYPES = _SUBSCRIPTION_EVENTS | {
    "checkout.session.completed",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
}


def _get(value: object, key: str, default: Any = None) -> Any:
    getter = getattr(value, "get", None)
    return getter(key, default) if callable(getter) else default


def _string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _object_id(value: object) -> str | None:
    return _string(value) or _string(_get(value, "id"))


def _metadata_candidates(obj: object) -> list[object]:
    """Return metadata exposed by Stripe object types used by this endpoint."""
    candidates = [_get(obj, "metadata", {})]
    subscription_details = _get(obj, "subscription_details")
    candidates.append(_get(subscription_details, "metadata", {}))
    parent = _get(obj, "parent")
    parent_subscription_details = _get(parent, "subscription_details")
    candidates.append(_get(parent_subscription_details, "metadata", {}))
    return candidates


def _metadata_value(obj: object, key: str) -> str | None:
    for metadata in _metadata_candidates(obj):
        value = _string(_get(metadata, key))
        if value:
            return value
    return None


def _subscription_id(event_type: str, obj: object) -> str | None:
    if event_type.startswith("customer.subscription."):
        return _object_id(_get(obj, "id"))

    direct = _object_id(_get(obj, "subscription"))
    if direct:
        return direct

    parent = _get(obj, "parent")
    subscription_details = _get(parent, "subscription_details")
    return _object_id(_get(subscription_details, "subscription"))


def _organization_target(
    db: Session,
    *,
    event_type: str,
    obj: object,
) -> _BillingTarget | None:
    """Resolve only a pre-existing workspace subscription from a Stripe event."""
    customer_id = _object_id(_get(obj, "customer"))
    stripe_subscription_id = _subscription_id(event_type, obj)
    metadata_org_id = _metadata_value(obj, "org_id")
    metadata_billing_owner_id = _metadata_value(obj, "billing_owner_user_id")

    subscription = None
    if stripe_subscription_id:
        subscription = db.scalar(
            select(OrganizationSubscription).where(
                OrganizationSubscription.stripe_subscription_id == stripe_subscription_id
            )
        )
    if subscription is None and customer_id:
        subscription = db.scalars(
            select(OrganizationSubscription)
            .where(OrganizationSubscription.stripe_customer_id == customer_id)
            .order_by(OrganizationSubscription.created_at.asc())
        ).first()
    if subscription is None and metadata_org_id:
        subscription = db.scalar(
            select(OrganizationSubscription).where(
                OrganizationSubscription.org_id == metadata_org_id
            )
        )

    if subscription is None:
        return None
    if metadata_org_id and metadata_org_id != subscription.org_id:
        return None
    if (
        metadata_billing_owner_id
        and metadata_billing_owner_id != subscription.billing_owner_user_id
    ):
        return None

    active_owner = db.scalar(
        select(OrganizationMembership.id).where(
            OrganizationMembership.org_id == subscription.org_id,
            OrganizationMembership.user_id == subscription.billing_owner_user_id,
            OrganizationMembership.status == ACTIVE_MEMBERSHIP_STATUS,
            OrganizationMembership.role == OWNER_ROLE,
        )
    )
    if active_owner is None:
        return None
    return _BillingTarget(
        scope="organization",
        user_id=subscription.billing_owner_user_id,
        org_id=subscription.org_id,
        subscription=subscription,
        stripe_customer_id=customer_id,
        stripe_subscription_id=stripe_subscription_id,
    )


def _resolve_subscription_target(
    db: Session,
    *,
    event_type: str,
    obj: object,
) -> _BillingTarget | None:
    """Resolve a local user/subscription without trusting a fallback plan."""
    organization_target = _organization_target(db, event_type=event_type, obj=obj)
    if organization_target is not None:
        return organization_target
    # Do not reinterpret a malformed organization event as a legacy user event.
    if _metadata_value(obj, "org_id") is not None:
        return None

    customer_id = _object_id(_get(obj, "customer"))
    stripe_subscription_id = _subscription_id(event_type, obj)
    metadata_user_id = _metadata_value(obj, "user_id") or _string(
        _get(obj, "client_reference_id")
    )

    subscription = None
    if stripe_subscription_id:
        subscription = db.scalar(
            select(Subscription).where(
                Subscription.stripe_subscription_id == stripe_subscription_id
            )
        )
    if subscription is None and customer_id:
        subscription = db.scalar(
            select(Subscription).where(Subscription.stripe_customer_id == customer_id)
        )

    if subscription is not None:
        if metadata_user_id and metadata_user_id != subscription.user_id:
            return None
        return _BillingTarget(
            scope="user",
            user_id=subscription.user_id,
            org_id=None,
            subscription=subscription,
            stripe_customer_id=customer_id,
            stripe_subscription_id=stripe_subscription_id,
        )

    if metadata_user_id and db.get(User, metadata_user_id) is not None:
        return _BillingTarget(
            scope="user",
            user_id=metadata_user_id,
            org_id=None,
            subscription=None,
            stripe_customer_id=customer_id,
            stripe_subscription_id=stripe_subscription_id,
        )

    return None


def _resolve_plan(
    obj: object,
    subscription: Subscription | OrganizationSubscription | None,
) -> str | None:
    plan = _metadata_value(obj, "plan")
    if plan in VALID_PLANS:
        return plan
    return subscription.plan if subscription is not None else None


def _is_stale(
    subscription: Subscription | OrganizationSubscription | None,
    event_created_at: int,
) -> bool:
    return bool(
        subscription is not None
        and subscription.stripe_state_event_created_at is not None
        and event_created_at < subscription.stripe_state_event_created_at
    )


def _now_naive_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _sync_subscription(
    db: Session,
    *,
    user_id: str,
    plan: str,
    status: str,
    customer_id: str | None,
    stripe_subscription_id: str | None,
    event_created_at: int,
) -> None:
    update_subscription_command(
        db,
        user_id,
        plan,
        status,
        stripe_customer_id=customer_id,
        stripe_subscription_id=stripe_subscription_id,
        stripe_state_event_created_at=event_created_at,
        commit=False,
    )


def _organization_subscription_item_state(
    obj: object,
) -> tuple[str | None, int, str | None] | None:
    """Read one licensed item quantity without guessing among multiple products."""
    items = _get(obj, "items")
    entries = _get(items, "data")
    if not isinstance(entries, (list, tuple)) or len(entries) != 1:
        return None
    quantity = _get(entries[0], "quantity")
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
        return None
    return (
        _object_id(_get(entries[0], "id")),
        quantity,
        _object_id(_get(entries[0], "price")),
    )


def _organization_plan_from_item(
    obj: object,
    subscription: OrganizationSubscription,
    seat_state: tuple[str | None, int, str | None] | None,
) -> str | None:
    """Prefer the actual Stripe Price when a Subscription item reports one."""
    if seat_state is not None:
        _item_id, _quantity, price_id = seat_state
        if price_id:
            for plan, configured_price_id in PLAN_PRICE_IDS.items():
                if configured_price_id and configured_price_id == price_id:
                    return plan
    return _resolve_plan(obj, subscription)


def _sync_organization_subscription(
    db: Session,
    *,
    target: _BillingTarget,
    plan: str,
    status: str,
    event_created_at: int,
    seat_state: tuple[str | None, int, str | None] | None = None,
) -> None:
    subscription = target.subscription
    if not isinstance(subscription, OrganizationSubscription):
        raise ValueError("Organization billing target is missing its subscription")

    stripe_subscription_item_id = subscription.stripe_subscription_item_id
    seat_limit = subscription.seat_limit
    billable_seat_count = subscription.billable_seat_count
    if seat_state is not None:
        stripe_subscription_item_id, seat_count, _price_id = seat_state
        seat_limit = seat_count
        billable_seat_count = seat_count

    upsert_organization_subscription_command(
        db,
        org_id=subscription.org_id,
        billing_owner_user_id=subscription.billing_owner_user_id,
        plan=plan,
        status=status,
        seat_limit=seat_limit,
        billable_seat_count=billable_seat_count,
        stripe_customer_id=target.stripe_customer_id or subscription.stripe_customer_id,
        stripe_subscription_id=(
            target.stripe_subscription_id or subscription.stripe_subscription_id
        ),
        stripe_subscription_item_id=stripe_subscription_item_id,
        stripe_state_event_created_at=event_created_at,
        commit=False,
    )


def _apply_stripe_event(
    db: Session,
    *,
    event_type: str,
    event_created_at: int,
    obj: object,
) -> str:
    if event_type not in _SUPPORTED_EVENT_TYPES:
        return "ignored_unsupported_event"

    target = _resolve_subscription_target(db, event_type=event_type, obj=obj)
    if target is None:
        return "ignored_unmapped"

    if _is_stale(target.subscription, event_created_at):
        return "ignored_stale"

    current_customer_id = target.stripe_customer_id or (
        target.subscription.stripe_customer_id if target.subscription is not None else None
    )
    current_subscription_id = target.stripe_subscription_id or (
        target.subscription.stripe_subscription_id if target.subscription is not None else None
    )

    if event_type == "checkout.session.completed":
        plan = _resolve_plan(obj, target.subscription)
        payment_status = _string(_get(obj, "payment_status"))
        if plan is None or payment_status not in {
            "paid",
            "no_payment_required",
            "unpaid",
        }:
            return "ignored_invalid_checkout"
        subscription_status = (
            "active"
            if payment_status in {"paid", "no_payment_required"}
            else "incomplete"
        )
        if target.scope == "organization":
            _sync_organization_subscription(
                db,
                target=replace(
                    target,
                    stripe_customer_id=current_customer_id,
                    stripe_subscription_id=current_subscription_id,
                ),
                plan=plan,
                status=subscription_status,
                event_created_at=event_created_at,
            )
            return "processed_organization_checkout"
        if target.user_id is None:
            return "ignored_unmapped"
        _sync_subscription(
            db,
            user_id=target.user_id,
            plan=plan,
            status=subscription_status,
            customer_id=current_customer_id,
            stripe_subscription_id=current_subscription_id,
            event_created_at=event_created_at,
        )
        return "processed_checkout"

    if event_type in _SUBSCRIPTION_EVENTS:
        seat_state = _organization_subscription_item_state(obj)
        plan = (
            _organization_plan_from_item(obj, target.subscription, seat_state)
            if isinstance(target.subscription, OrganizationSubscription)
            else _resolve_plan(obj, target.subscription)
        )
        current_subscription_status = _string(_get(obj, "status"))
        if plan is None or current_subscription_status not in VALID_SUBSCRIPTION_STATUSES:
            return "ignored_invalid_subscription"
        if target.scope == "organization":
            _sync_organization_subscription(
                db,
                target=replace(
                    target,
                    stripe_customer_id=current_customer_id,
                    stripe_subscription_id=current_subscription_id,
                ),
                plan=plan,
                status=current_subscription_status,
                event_created_at=event_created_at,
                seat_state=seat_state,
            )
            return "processed_organization_subscription"
        if target.user_id is None:
            return "ignored_unmapped"
        _sync_subscription(
            db,
            user_id=target.user_id,
            plan=plan,
            status=current_subscription_status,
            customer_id=current_customer_id,
            stripe_subscription_id=current_subscription_id,
            event_created_at=event_created_at,
        )
        return "processed_subscription"

    if event_type == "customer.subscription.deleted":
        if target.scope == "organization":
            _sync_organization_subscription(
                db,
                target=replace(
                    target,
                    stripe_customer_id=current_customer_id,
                    stripe_subscription_id=current_subscription_id,
                ),
                plan="starter",
                status="canceled",
                event_created_at=event_created_at,
            )
            return "processed_organization_cancellation"
        if target.user_id is None:
            return "ignored_unmapped"
        _sync_subscription(
            db,
            user_id=target.user_id,
            plan="starter",
            status="canceled",
            customer_id=current_customer_id,
            stripe_subscription_id=current_subscription_id,
            event_created_at=event_created_at,
        )
        return "processed_cancellation"

    plan = _resolve_plan(obj, target.subscription)
    if plan is None:
        return "ignored_invalid_invoice"
    invoice_status = "active" if event_type == "invoice.paid" else "past_due"
    if target.scope == "organization":
        _sync_organization_subscription(
            db,
            target=replace(
                target,
                stripe_customer_id=current_customer_id,
                stripe_subscription_id=current_subscription_id,
            ),
            plan=plan,
            status=invoice_status,
            event_created_at=event_created_at,
        )
        return "processed_organization_invoice"
    if target.user_id is None:
        return "ignored_unmapped"
    _sync_subscription(
        db,
        user_id=target.user_id,
        plan=plan,
        status=invoice_status,
        customer_id=current_customer_id,
        stripe_subscription_id=current_subscription_id,
        event_created_at=event_created_at,
    )
    return "processed_invoice"


def process_stripe_webhook_event(
    db: Session,
    event: object,
) -> StripeWebhookProcessResult:
    """Apply one verified Stripe event exactly once within a DB transaction.

    Stripe can retry duplicate events and delivers events out of order. The
    receipt ledger stops replays while the subscription event timestamp stops a
    delayed state transition from overriding a newer one.
    """
    event_id = _string(_get(event, "id"))
    event_type = _string(_get(event, "type"))
    event_created_at = _get(event, "created")
    if (
        event_id is None
        or event_type is None
        or not isinstance(event_created_at, int)
        or isinstance(event_created_at, bool)
        or event_created_at < 0
    ):
        raise ValueError("Malformed Stripe event")

    data = _get(event, "data")
    obj = _get(data, "object")
    if obj is None:
        raise ValueError("Malformed Stripe event payload")

    receipt = StripeWebhookEvent(
        event_id=event_id,
        event_type=event_type,
        event_created_at=event_created_at,
        livemode=bool(_get(event, "livemode", False)),
        outcome="received",
    )
    db.add(receipt)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return StripeWebhookProcessResult(outcome="duplicate", duplicate=True)

    try:
        target = _resolve_subscription_target(
            db,
            event_type=event_type,
            obj=obj,
        )
        if target is not None:
            receipt.user_id = target.user_id
            receipt.org_id = target.org_id
            receipt.stripe_customer_id = target.stripe_customer_id
            receipt.stripe_subscription_id = target.stripe_subscription_id
        outcome = _apply_stripe_event(
            db,
            event_type=event_type,
            event_created_at=event_created_at,
            obj=obj,
        )
        receipt.outcome = outcome
        receipt.processed_at = _now_naive_utc()
        db.commit()
    except Exception:
        db.rollback()
        raise

    return StripeWebhookProcessResult(outcome=outcome)


def list_stripe_webhook_receipts(
    db: Session,
    *,
    user_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    """Return a support-safe view of webhook reconciliation, never raw payloads."""
    safe_limit = min(max(limit, 1), 200)
    statement = select(StripeWebhookEvent).order_by(
        StripeWebhookEvent.received_at.desc()
    )
    if user_id is not None:
        statement = statement.where(StripeWebhookEvent.user_id == user_id)
    events = list(db.scalars(statement.limit(safe_limit)))
    return [
        {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "event_created_at": event.event_created_at,
            "livemode": event.livemode,
            "outcome": event.outcome,
            "org_id": event.org_id,
            "stripe_customer_id": event.stripe_customer_id,
            "stripe_subscription_id": event.stripe_subscription_id,
            "received_at": event.received_at.isoformat() if event.received_at else "",
            "processed_at": event.processed_at.isoformat() if event.processed_at else None,
        }
        for event in events
    ]


def get_billing_summary(
    db: Session,
    user_id: str | None = None,
    *,
    org_id: str | None = None,
    actor_user_id: str | None = None,
) -> BillingSummaryRead:
    """Read the commercial state of one active organization workspace."""
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

    entitlement = resolve_org_entitlements(
        db,
        org_id=org_id,
        actor_user_id=actor_user_id,
    )
    quota = get_usage_quota(
        db,
        org_id=org_id,
        actor_user_id=actor_user_id,
    )
    return BillingSummaryRead(
        plan=quota.plan,
        status=entitlement.subscription_status,
        stripe_customer_id=entitlement.stripe_customer_id,
        entitlement_source=entitlement.source,
        seat_limit=entitlement.seat_limit,
        is_billing_owner=entitlement.is_billing_owner,
        monthly_workflow_limit=quota.monthly_workflow_limit,
        monthly_workflow_used=quota.monthly_workflow_used,
        monthly_workflow_remaining=quota.monthly_workflow_remaining,
        monthly_assistant_limit=quota.monthly_assistant_limit,
        monthly_assistant_used=quota.monthly_assistant_used,
        monthly_assistant_remaining=quota.monthly_assistant_remaining,
        monthly_indexing_limit=quota.monthly_indexing_limit,
        monthly_indexing_used=quota.monthly_indexing_used,
        monthly_indexing_remaining=quota.monthly_indexing_remaining,
        official_model_usage=quota.official_model_usage,
        byok_model_usage=quota.byok_model_usage,
        trial_window_start=quota.trial_window_start,
    )
