"""Route-level tests for Stripe checkout, portal, and webhook boundaries."""

from unittest.mock import patch

from app.adapters.stripe_adapter import BillingPortalResult, CheckoutResult
from app.billing.service import StripeWebhookProcessResult
from app.models import OrganizationMembership, OrganizationSubscription, Subscription


def _clear_dev_billing_state(test_db, default_user_id: str, default_org_id: str) -> None:
    test_db.query(Subscription).filter_by(user_id=default_user_id).delete()
    test_db.query(OrganizationSubscription).filter_by(org_id=default_org_id).delete()
    test_db.commit()


def test_checkout_returns_501_when_stripe_not_configured(client):
    with patch("app.billing.router.is_stripe_configured", return_value=False):
        resp = client.post("/billing/checkout?plan=professional")
    assert resp.status_code == 501


def test_checkout_returns_400_for_invalid_plan(client):
    with patch("app.billing.router.is_stripe_configured", return_value=True):
        resp = client.post("/billing/checkout?plan=starter")
    assert resp.status_code == 400


@patch("app.billing.router.is_stripe_configured", return_value=True)
@patch("app.billing.router.create_organization_checkout_session")
def test_checkout_returns_url_on_success(
    mock_checkout,
    _mock_configured,
    client,
    test_db,
    default_user_id: str,
    default_org_id: str,
):
    _clear_dev_billing_state(test_db, default_user_id, default_org_id)
    mock_checkout.return_value = CheckoutResult(
        session_id="cs_test_123", url="https://checkout.stripe.com/test"
    )

    resp = client.post("/billing/checkout?plan=professional")

    assert resp.status_code == 200
    assert resp.json() == {
        "url": "https://checkout.stripe.com/test",
        "session_id": "cs_test_123",
        "mode": "checkout",
    }
    mock_checkout.assert_called_once()
    assert mock_checkout.call_args.kwargs["org_id"] == default_org_id
    assert mock_checkout.call_args.kwargs["billing_owner_user_id"] == default_user_id
    active_members = test_db.query(OrganizationMembership).filter_by(
        org_id=default_org_id,
        status="active",
    ).count()
    assert mock_checkout.call_args.kwargs["seat_count"] == max(1, active_members)


@patch("app.billing.router.is_stripe_configured", return_value=True)
@patch("app.billing.router.create_billing_portal_session")
@patch("app.billing.router.create_organization_checkout_session")
def test_checkout_uses_portal_for_existing_stripe_customer(
    mock_checkout,
    mock_portal,
    _mock_configured,
    client,
    test_db,
    default_user_id: str,
    default_org_id: str,
):
    _clear_dev_billing_state(test_db, default_user_id, default_org_id)
    test_db.add(
        OrganizationSubscription(
            org_id=default_org_id,
            billing_owner_user_id=default_user_id,
            plan="professional",
            status="active",
            seat_limit=1,
            billable_seat_count=1,
            stripe_customer_id="cus_existing",
        )
    )
    test_db.commit()
    mock_portal.return_value = BillingPortalResult(
        session_id="bps_test_123", url="https://billing.stripe.com/session/test"
    )

    resp = client.post("/billing/checkout?plan=enterprise")

    assert resp.status_code == 200
    assert resp.json()["mode"] == "portal"
    assert resp.json()["url"] == "https://billing.stripe.com/session/test"
    mock_portal.assert_called_once()
    mock_checkout.assert_not_called()
    _clear_dev_billing_state(test_db, default_user_id, default_org_id)


@patch("app.billing.router.is_stripe_configured", return_value=True)
@patch("app.billing.router.create_billing_portal_session")
def test_portal_returns_url_for_linked_customer(
    mock_portal,
    _mock_configured,
    client,
    test_db,
    default_user_id: str,
    default_org_id: str,
):
    _clear_dev_billing_state(test_db, default_user_id, default_org_id)
    test_db.add(
        OrganizationSubscription(
            org_id=default_org_id,
            billing_owner_user_id=default_user_id,
            plan="professional",
            status="active",
            seat_limit=1,
            billable_seat_count=1,
            stripe_customer_id="cus_portal",
        )
    )
    test_db.commit()
    mock_portal.return_value = BillingPortalResult(
        session_id="bps_test_456", url="https://billing.stripe.com/session/portal"
    )

    resp = client.post("/billing/portal")

    assert resp.status_code == 200
    assert resp.json()["url"] == "https://billing.stripe.com/session/portal"
    mock_portal.assert_called_once()
    _clear_dev_billing_state(test_db, default_user_id, default_org_id)


def test_portal_returns_409_without_linked_customer(client, test_db, default_user_id: str, default_org_id: str):
    _clear_dev_billing_state(test_db, default_user_id, default_org_id)
    with patch("app.billing.router.is_stripe_configured", return_value=True):
        resp = client.post("/billing/portal")
    assert resp.status_code == 409


@patch("app.billing.router.is_stripe_configured", return_value=True)
def test_checkout_refuses_to_attach_legacy_customer_to_workspace(
    _mock_configured,
    client,
    test_db,
    default_user_id: str,
    default_org_id: str,
):
    _clear_dev_billing_state(test_db, default_user_id, default_org_id)
    test_db.add(
        Subscription(
            user_id=default_user_id,
            plan="professional",
            status="active",
            stripe_customer_id="cus_legacy",
        )
    )
    test_db.commit()

    resp = client.post("/billing/checkout?plan=professional")

    assert resp.status_code == 409
    _clear_dev_billing_state(test_db, default_user_id, default_org_id)


@patch("app.billing.router.is_stripe_configured", return_value=True)
def test_checkout_requires_workspace_billing_owner(
    _mock_configured,
    client,
    test_db,
    default_user_id: str,
    default_org_id: str,
):
    _clear_dev_billing_state(test_db, default_user_id, default_org_id)
    membership = test_db.query(OrganizationMembership).filter_by(
        org_id=default_org_id,
        user_id=default_user_id,
    ).one()
    original_role = membership.role
    membership.role = "member"
    test_db.commit()
    try:
        resp = client.post("/billing/checkout?plan=professional")
        assert resp.status_code == 403
    finally:
        membership.role = original_role
        test_db.commit()


def test_webhook_returns_400_on_bad_signature(client):
    with patch("app.billing.router.verify_webhook_signature", side_effect=ValueError("bad sig")):
        resp = client.post(
            "/billing/webhook",
            content=b"{}",
            headers={"Stripe-Signature": "bad_sig"},
        )
    assert resp.status_code == 400


@patch("app.billing.router.process_stripe_webhook_event")
@patch("app.billing.router.verify_webhook_signature")
def test_webhook_delegates_verified_event(mock_verify, mock_process, client):
    event = {
        "id": "evt_router_1",
        "type": "checkout.session.completed",
        "created": 100,
        "data": {"object": {}},
    }
    mock_verify.return_value = event
    mock_process.return_value = StripeWebhookProcessResult(outcome="processed_checkout")

    resp = client.post(
        "/billing/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=abc"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"received": True, "duplicate": False}
    mock_process.assert_called_once()


@patch("app.billing.router.process_stripe_webhook_event", side_effect=ValueError("bad event"))
@patch("app.billing.router.verify_webhook_signature")
def test_webhook_rejects_malformed_signed_event(mock_verify, _mock_process, client):
    mock_verify.return_value = {"id": "evt_bad"}
    resp = client.post(
        "/billing/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=abc"},
    )
    assert resp.status_code == 400
