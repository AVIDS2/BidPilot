"""Contract tests for the Stripe SDK adapter without network access."""

import sys
from types import SimpleNamespace
from unittest.mock import patch

from app.adapters import stripe_adapter


def test_checkout_copies_correlation_metadata_to_subscription(monkeypatch):
    calls: list[dict] = []

    class FakeCheckoutSession:
        @staticmethod
        def create(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(id="cs_test_123", url="https://checkout.stripe.com/test")

    fake_stripe = SimpleNamespace(
        api_key=None,
        checkout=SimpleNamespace(Session=FakeCheckoutSession),
    )
    monkeypatch.setattr(stripe_adapter, "_STRIPE_KEY", "sk_test_adapter")
    monkeypatch.setitem(stripe_adapter.PLAN_PRICE_IDS, "professional", "price_professional")

    with patch.dict(sys.modules, {"stripe": fake_stripe}):
        result = stripe_adapter.create_checkout_session(
            user_id="user_123",
            user_email="user@example.com",
            plan="professional",
            success_url="https://app.example/success",
            cancel_url="https://app.example/cancel",
        )

    assert result.session_id == "cs_test_123"
    assert calls == [
        {
            "mode": "subscription",
            "success_url": "https://app.example/success",
            "cancel_url": "https://app.example/cancel",
            "line_items": [{"price": "price_professional", "quantity": 1}],
            "client_reference_id": "user_123",
            "metadata": {"user_id": "user_123", "plan": "professional"},
            "subscription_data": {
                "metadata": {"user_id": "user_123", "plan": "professional"}
            },
            "customer_email": "user@example.com",
        }
    ]


def test_checkout_uses_existing_customer_instead_of_customer_email(monkeypatch):
    calls: list[dict] = []

    class FakeCheckoutSession:
        @staticmethod
        def create(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(id="cs_test_456", url="https://checkout.stripe.com/test")

    fake_stripe = SimpleNamespace(
        api_key=None,
        checkout=SimpleNamespace(Session=FakeCheckoutSession),
    )
    monkeypatch.setattr(stripe_adapter, "_STRIPE_KEY", "sk_test_adapter")
    monkeypatch.setitem(stripe_adapter.PLAN_PRICE_IDS, "professional", "price_professional")

    with patch.dict(sys.modules, {"stripe": fake_stripe}):
        stripe_adapter.create_checkout_session(
            user_id="user_456",
            user_email="ignored@example.com",
            plan="professional",
            success_url="https://app.example/success",
            cancel_url="https://app.example/cancel",
            stripe_customer_id="cus_existing",
        )

    assert calls[0]["customer"] == "cus_existing"
    assert "customer_email" not in calls[0]


def test_organization_checkout_copies_workspace_metadata_and_seat_quantity(monkeypatch):
    calls: list[dict] = []

    class FakeCheckoutSession:
        @staticmethod
        def create(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(id="cs_test_org_123", url="https://checkout.stripe.com/test")

    fake_stripe = SimpleNamespace(
        api_key=None,
        checkout=SimpleNamespace(Session=FakeCheckoutSession),
    )
    monkeypatch.setattr(stripe_adapter, "_STRIPE_KEY", "sk_test_adapter")
    monkeypatch.setitem(stripe_adapter.PLAN_PRICE_IDS, "professional", "price_professional")

    with patch.dict(sys.modules, {"stripe": fake_stripe}):
        result = stripe_adapter.create_organization_checkout_session(
            org_id="org_123",
            billing_owner_user_id="user_owner",
            billing_owner_email="owner@example.com",
            plan="professional",
            seat_count=4,
            success_url="https://app.example/success",
            cancel_url="https://app.example/cancel",
        )

    metadata = {
        "org_id": "org_123",
        "billing_owner_user_id": "user_owner",
        "plan": "professional",
    }
    assert result.session_id == "cs_test_org_123"
    assert calls == [
        {
            "mode": "subscription",
            "success_url": "https://app.example/success",
            "cancel_url": "https://app.example/cancel",
            "line_items": [{"price": "price_professional", "quantity": 4}],
            "client_reference_id": "org_123",
            "metadata": metadata,
            "subscription_data": {"metadata": metadata},
            "customer_email": "owner@example.com",
        }
    ]


def test_billing_portal_returns_stripe_hosted_url(monkeypatch):
    calls: list[dict] = []

    class FakePortalSession:
        @staticmethod
        def create(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(id="bps_test_123", url="https://billing.stripe.com/session/test")

    fake_stripe = SimpleNamespace(
        api_key=None,
        billing_portal=SimpleNamespace(Session=FakePortalSession),
    )
    monkeypatch.setattr(stripe_adapter, "_STRIPE_KEY", "sk_test_adapter")

    with patch.dict(sys.modules, {"stripe": fake_stripe}):
        result = stripe_adapter.create_billing_portal_session(
            stripe_customer_id="cus_portal",
            return_url="https://app.example/account",
        )

    assert result.session_id == "bps_test_123"
    assert result.url == "https://billing.stripe.com/session/test"
    assert calls == [
        {"customer": "cus_portal", "return_url": "https://app.example/account"}
    ]
