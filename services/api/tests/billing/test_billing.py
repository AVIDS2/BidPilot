"""Tests for billing checkout and webhook endpoints.

Stripe adapter calls are mocked so tests run without a real Stripe key.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_checkout_returns_501_when_stripe_not_configured():
    with patch("app.billing.router.is_stripe_configured", return_value=False):
        resp = client.post("/billing/checkout?plan=professional")
        assert resp.status_code == 501


def test_checkout_returns_400_for_invalid_plan():
    with patch("app.billing.router.is_stripe_configured", return_value=True):
        resp = client.post("/billing/checkout?plan=starter")
        assert resp.status_code == 400


@patch("app.billing.router.is_stripe_configured", return_value=True)
@patch("app.billing.router.create_checkout_session")
def test_checkout_returns_url_on_success(mock_checkout, _mock_configured):
    from app.adapters.stripe_adapter import CheckoutResult
    mock_checkout.return_value = CheckoutResult(
        session_id="cs_test_123", url="https://checkout.stripe.com/test"
    )
    resp = client.post("/billing/checkout?plan=professional")
    assert resp.status_code == 200
    data = resp.json()
    assert data["url"] == "https://checkout.stripe.com/test"
    assert data["session_id"] == "cs_test_123"


def test_webhook_returns_400_on_bad_signature():
    with patch("app.billing.router.verify_webhook_signature", side_effect=ValueError("bad sig")):
        resp = client.post(
            "/billing/webhook",
            content=b"{}",
            headers={"Stripe-Signature": "bad_sig"},
        )
        assert resp.status_code == 400


@patch("app.billing.router.update_subscription_command")
@patch("app.billing.router.verify_webhook_signature")
def test_webhook_handles_checkout_completed(mock_verify, mock_update):
    mock_verify.return_value = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"user_id": "some-user", "plan": "professional"},
            }
        },
    }
    resp = client.post(
        "/billing/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=abc"},
    )
    assert resp.status_code == 200
    assert resp.json()["received"] is True
    mock_update.assert_called_once()
    call_args = mock_update.call_args
    assert call_args[0][1] == "some-user"
    assert call_args[0][2] == "professional"
    assert call_args[0][3] == "active"


@patch("app.billing.router.update_subscription_command")
@patch("app.billing.router.verify_webhook_signature")
def test_webhook_handles_subscription_deleted(mock_verify, mock_update):
    mock_verify.return_value = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "metadata": {"user_id": "some-user"},
            }
        },
    }
    resp = client.post(
        "/billing/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=abc"},
    )
    assert resp.status_code == 200
    mock_update.assert_called_once()
    call_args = mock_update.call_args
    assert call_args[0][2] == "starter"
    assert call_args[0][3] == "canceled"


@patch("app.billing.router.update_subscription_command")
@patch("app.billing.router.verify_webhook_signature")
def test_webhook_handles_subscription_updated(mock_verify, mock_update):
    mock_verify.return_value = {
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "status": "past_due",
                "metadata": {"user_id": "some-user", "plan": "professional"},
            }
        },
    }
    resp = client.post(
        "/billing/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=abc"},
    )
    assert resp.status_code == 200
    mock_update.assert_called_once()
    call_args = mock_update.call_args
    assert call_args[0][1] == "some-user"
    assert call_args[0][2] == "professional"
    assert call_args[0][3] == "past_due"


@patch("app.billing.router.update_subscription_command")
@patch("app.billing.router.verify_webhook_signature")
def test_webhook_handles_invoice_payment_failed(mock_verify, mock_update):
    mock_verify.return_value = {
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "metadata": {"user_id": "some-user", "plan": "professional"},
            }
        },
    }
    resp = client.post(
        "/billing/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=abc"},
    )
    assert resp.status_code == 200
    mock_update.assert_called_once()
    call_args = mock_update.call_args
    assert call_args[0][1] == "some-user"
    assert call_args[0][2] == "professional"
    assert call_args[0][3] == "past_due"


@patch("app.billing.router.verify_webhook_signature")
def test_webhook_ignores_unknown_event(mock_verify):
    mock_verify.return_value = {
        "type": "payment_intent.succeeded",
        "data": {"object": {}},
    }
    resp = client.post(
        "/billing/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=abc"},
    )
    assert resp.status_code == 200
