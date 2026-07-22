"""Persistence and entitlement tests for the Stripe webhook control plane."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.stripe_adapter import PLAN_PRICE_IDS
from app.auth.service import _hash_password
from app.billing.service import process_stripe_webhook_event
from app.db import Base
from app.models import (
    Organization,
    OrganizationMembership,
    OrganizationSubscription,
    StripeWebhookEvent,
    Subscription,
    User,
)
from app.usage.service import get_user_plan


def _make_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add(
        Organization(
            id="00000000-0000-0000-0000-000000000001",
            slug="billing-test",
            name="Billing Test",
        )
    )
    session.commit()
    return session


def _make_user(db: Session) -> User:
    user = User(
        email="billing@example.com",
        display_name="Billing Test",
        password_hash=_hash_password("Test1234"),
        org_id="00000000-0000-0000-0000-000000000001",
    )
    db.add(user)
    db.flush()
    db.add(
        OrganizationMembership(
            org_id="00000000-0000-0000-0000-000000000001",
            user_id=user.id,
            role="owner",
        )
    )
    db.add(Subscription(user_id=user.id, plan="starter", status="active"))
    db.commit()
    return user


def _event(event_id: str, event_type: str, created: int, obj: dict) -> dict:
    return {
        "id": event_id,
        "type": event_type,
        "created": created,
        "livemode": False,
        "data": {"object": obj},
    }


def _make_organization_subscription(db: Session, user: User) -> OrganizationSubscription:
    subscription = OrganizationSubscription(
        org_id=user.org_id,
        billing_owner_user_id=user.id,
        plan="starter",
        status="active",
        seat_limit=1,
        billable_seat_count=1,
    )
    db.add(subscription)
    db.commit()
    return subscription


def test_checkout_receipt_persists_stripe_mappings_and_plan():
    db = _make_db()
    try:
        user = _make_user(db)
        result = process_stripe_webhook_event(
            db,
            _event(
                "evt_checkout_1",
                "checkout.session.completed",
                100,
                {
                    "metadata": {"user_id": user.id, "plan": "professional"},
                    "client_reference_id": user.id,
                    "customer": "cus_checkout",
                    "subscription": "sub_checkout",
                    "payment_status": "paid",
                },
            ),
        )

        sub = db.query(Subscription).filter_by(user_id=user.id).one()
        receipt = db.get(StripeWebhookEvent, "evt_checkout_1")
        assert result.outcome == "processed_checkout"
        assert sub.plan == "professional"
        assert sub.status == "active"
        assert sub.stripe_customer_id == "cus_checkout"
        assert sub.stripe_subscription_id == "sub_checkout"
        assert sub.stripe_state_event_created_at == 100
        assert receipt is not None and receipt.outcome == "processed_checkout"
        assert receipt.user_id == user.id
        assert receipt.stripe_customer_id == "cus_checkout"
        assert receipt.stripe_subscription_id == "sub_checkout"
    finally:
        db.close()


def test_subscription_event_uses_subscription_metadata_for_mapping():
    db = _make_db()
    try:
        user = _make_user(db)
        result = process_stripe_webhook_event(
            db,
            _event(
                "evt_subscription_1",
                "customer.subscription.updated",
                200,
                {
                    "id": "sub_metadata",
                    "customer": "cus_metadata",
                    "status": "trialing",
                    "metadata": {"user_id": user.id, "plan": "enterprise"},
                },
            ),
        )

        sub = db.query(Subscription).filter_by(user_id=user.id).one()
        assert result.outcome == "processed_subscription"
        assert sub.plan == "enterprise"
        assert sub.status == "trialing"
        assert sub.stripe_subscription_id == "sub_metadata"
    finally:
        db.close()


def test_invoice_failure_uses_transferred_subscription_metadata():
    db = _make_db()
    try:
        user = _make_user(db)
        result = process_stripe_webhook_event(
            db,
            _event(
                "evt_invoice_failed_1",
                "invoice.payment_failed",
                300,
                {
                    "customer": "cus_invoice",
                    "subscription_details": {
                        "metadata": {"user_id": user.id, "plan": "professional"}
                    },
                },
            ),
        )

        sub = db.query(Subscription).filter_by(user_id=user.id).one()
        assert result.outcome == "processed_invoice"
        assert sub.plan == "professional"
        assert sub.status == "past_due"
        assert sub.stripe_customer_id == "cus_invoice"
    finally:
        db.close()


def test_duplicate_event_is_recorded_once_and_not_reapplied():
    db = _make_db()
    try:
        user = _make_user(db)
        event = _event(
            "evt_duplicate_1",
            "checkout.session.completed",
            400,
            {
                "metadata": {"user_id": user.id, "plan": "professional"},
                "customer": "cus_duplicate",
                "subscription": "sub_duplicate",
                "payment_status": "paid",
            },
        )
        first = process_stripe_webhook_event(db, event)
        second = process_stripe_webhook_event(db, event)

        assert first.duplicate is False
        assert second.duplicate is True
        assert db.query(StripeWebhookEvent).count() == 1
    finally:
        db.close()


def test_stale_event_cannot_override_newer_subscription_state():
    db = _make_db()
    try:
        user = _make_user(db)
        current = _event(
            "evt_current_1",
            "customer.subscription.updated",
            600,
            {
                "id": "sub_ordered",
                "customer": "cus_ordered",
                "status": "past_due",
                "metadata": {"user_id": user.id, "plan": "professional"},
            },
        )
        stale = _event(
            "evt_stale_1",
            "customer.subscription.updated",
            500,
            {
                "id": "sub_ordered",
                "customer": "cus_ordered",
                "status": "active",
                "metadata": {"user_id": user.id, "plan": "professional"},
            },
        )
        process_stripe_webhook_event(db, current)
        result = process_stripe_webhook_event(db, stale)

        sub = db.query(Subscription).filter_by(user_id=user.id).one()
        assert result.outcome == "ignored_stale"
        assert sub.status == "past_due"
        assert sub.stripe_state_event_created_at == 600
    finally:
        db.close()


def test_non_entitled_stripe_status_reverts_effective_plan_to_starter():
    db = _make_db()
    try:
        user = _make_user(db)
        sub = db.query(Subscription).filter_by(user_id=user.id).one()
        sub.plan = "professional"
        sub.status = "unpaid"
        db.commit()

        assert get_user_plan(db, user.id) == "starter"
    finally:
        db.close()


def test_organization_checkout_maps_to_existing_workspace_subscription():
    db = _make_db()
    try:
        user = _make_user(db)
        organization_subscription = _make_organization_subscription(db, user)
        result = process_stripe_webhook_event(
            db,
            _event(
                "evt_org_checkout_1",
                "checkout.session.completed",
                700,
                {
                    "metadata": {
                        "org_id": user.org_id,
                        "billing_owner_user_id": user.id,
                        "plan": "professional",
                    },
                    "client_reference_id": user.org_id,
                    "customer": "cus_org_checkout",
                    "subscription": "sub_org_checkout",
                    "payment_status": "paid",
                },
            ),
        )

        db.refresh(organization_subscription)
        receipt = db.get(StripeWebhookEvent, "evt_org_checkout_1")
        assert result.outcome == "processed_organization_checkout"
        assert organization_subscription.plan == "professional"
        assert organization_subscription.status == "active"
        assert organization_subscription.stripe_customer_id == "cus_org_checkout"
        assert organization_subscription.stripe_subscription_id == "sub_org_checkout"
        assert organization_subscription.seat_limit == 1
        assert receipt is not None and receipt.org_id == user.org_id
    finally:
        db.close()


def test_organization_subscription_quantity_sets_paid_seat_capacity():
    db = _make_db()
    try:
        user = _make_user(db)
        organization_subscription = _make_organization_subscription(db, user)
        organization_subscription.plan = "professional"
        organization_subscription.stripe_subscription_id = "sub_org_quantity"
        db.commit()

        result = process_stripe_webhook_event(
            db,
            _event(
                "evt_org_subscription_1",
                "customer.subscription.updated",
                800,
                {
                    "id": "sub_org_quantity",
                    "customer": "cus_org_quantity",
                    "status": "active",
                    "metadata": {
                        "org_id": user.org_id,
                        "billing_owner_user_id": user.id,
                        "plan": "professional",
                    },
                    "items": {"data": [{"id": "si_org_quantity", "quantity": 4}]},
                },
            ),
        )

        db.refresh(organization_subscription)
        assert result.outcome == "processed_organization_subscription"
        assert organization_subscription.seat_limit == 4
        assert organization_subscription.billable_seat_count == 4
        assert organization_subscription.stripe_subscription_item_id == "si_org_quantity"
    finally:
        db.close()


def test_organization_subscription_uses_actual_price_to_reconcile_plan(monkeypatch):
    db = _make_db()
    try:
        user = _make_user(db)
        organization_subscription = _make_organization_subscription(db, user)
        organization_subscription.plan = "professional"
        organization_subscription.stripe_subscription_id = "sub_org_plan_switch"
        db.commit()
        monkeypatch.setitem(PLAN_PRICE_IDS, "enterprise", "price_enterprise")

        result = process_stripe_webhook_event(
            db,
            _event(
                "evt_org_plan_switch_1",
                "customer.subscription.updated",
                850,
                {
                    "id": "sub_org_plan_switch",
                    "customer": "cus_org_plan_switch",
                    "status": "active",
                    # This metadata is intentionally stale after a Portal plan change.
                    "metadata": {
                        "org_id": user.org_id,
                        "billing_owner_user_id": user.id,
                        "plan": "professional",
                    },
                    "items": {
                        "data": [
                            {
                                "id": "si_org_plan_switch",
                                "quantity": 2,
                                "price": {"id": "price_enterprise"},
                            }
                        ]
                    },
                },
            ),
        )

        db.refresh(organization_subscription)
        assert result.outcome == "processed_organization_subscription"
        assert organization_subscription.plan == "enterprise"
        assert organization_subscription.seat_limit == 2
    finally:
        db.close()


def test_organization_event_with_wrong_billing_owner_is_safely_ignored():
    db = _make_db()
    try:
        user = _make_user(db)
        organization_subscription = _make_organization_subscription(db, user)
        result = process_stripe_webhook_event(
            db,
            _event(
                "evt_org_wrong_owner_1",
                "checkout.session.completed",
                900,
                {
                    "metadata": {
                        "org_id": user.org_id,
                        "billing_owner_user_id": "different-owner",
                        "plan": "professional",
                    },
                    "customer": "cus_wrong_owner",
                    "subscription": "sub_wrong_owner",
                    "payment_status": "paid",
                },
            ),
        )

        db.refresh(organization_subscription)
        receipt = db.get(StripeWebhookEvent, "evt_org_wrong_owner_1")
        assert result.outcome == "ignored_unmapped"
        assert organization_subscription.plan == "starter"
        assert receipt is not None and receipt.org_id is None
    finally:
        db.close()
