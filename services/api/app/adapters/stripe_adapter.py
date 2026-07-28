"""Stripe adapter — wraps Stripe API calls behind a thin interface.

Environment variables:
  DOCPILOT_STRIPE_SECRET_KEY   – Stripe secret key (sk_test_… / sk_live_…)
  DOCPILOT_STRIPE_WEBHOOK_SECRET – Webhook signing secret (whsec_…)
  DOCPILOT_STRIPE_PRO_PRICE_ID   – Price ID for the Professional plan
  DOCPILOT_STRIPE_ENTERPRISE_PRICE_ID – Price ID for the Enterprise plan (optional)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

_STRIPE_KEY = os.environ.get("DOCPILOT_STRIPE_SECRET_KEY", "")
_STRIPE_WEBHOOK_SECRET = os.environ.get("DOCPILOT_STRIPE_WEBHOOK_SECRET", "")
_PRO_PRICE_ID = os.environ.get("DOCPILOT_STRIPE_PRO_PRICE_ID", "")
_ENTERPRISE_PRICE_ID = os.environ.get("DOCPILOT_STRIPE_ENTERPRISE_PRICE_ID", "")

PLAN_PRICE_IDS: dict[str, str] = {
    "professional": _PRO_PRICE_ID,
    "enterprise": _ENTERPRISE_PRICE_ID,
}


@dataclass
class CheckoutResult:
    session_id: str
    url: str


@dataclass
class BillingPortalResult:
    session_id: str
    url: str


def create_checkout_session(
    user_id: str,
    user_email: str,
    plan: str,
    success_url: str,
    cancel_url: str,
    stripe_customer_id: str | None = None,
) -> CheckoutResult:
    """Create a Stripe Checkout Session for a subscription upgrade.

    Returns the session ID and URL to redirect the user to.
    Raises RuntimeError if Stripe is not configured or the plan has no price ID.
    """
    if not _STRIPE_KEY:
        raise RuntimeError("Stripe is not configured (DOCPILOT_STRIPE_SECRET_KEY missing)")

    price_id = PLAN_PRICE_IDS.get(plan)
    if not price_id:
        raise RuntimeError(f"No Stripe price ID configured for plan '{plan}'")

    import stripe as _stripe
    _stripe.api_key = _STRIPE_KEY

    metadata = {"user_id": user_id, "plan": plan}
    session_args: dict[str, Any] = {
        "mode": "subscription",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "line_items": [{"price": price_id, "quantity": 1}],
        # Keep the Checkout event link and the resulting Subscription link.
        "client_reference_id": user_id,
        "metadata": metadata,
        "subscription_data": {"metadata": metadata},
    }
    if stripe_customer_id:
        session_args["customer"] = stripe_customer_id
    else:
        session_args["customer_email"] = user_email

    session = _stripe.checkout.Session.create(**session_args)
    if not session.url:
        raise RuntimeError("Stripe Checkout did not return a redirect URL")
    return CheckoutResult(session_id=session.id, url=session.url)


def create_organization_checkout_session(
    *,
    org_id: str,
    billing_owner_user_id: str,
    billing_owner_email: str,
    plan: str,
    seat_count: int,
    success_url: str,
    cancel_url: str,
    stripe_customer_id: str | None = None,
) -> CheckoutResult:
    """Create one organization-owned, licensed-seat subscription Checkout.

    Session and Subscription metadata are intentionally duplicated because
    Stripe emits them on different webhook object types.
    """
    if not _STRIPE_KEY:
        raise RuntimeError("Stripe is not configured (DOCPILOT_STRIPE_SECRET_KEY missing)")
    if seat_count < 1:
        raise ValueError("seat_count must be at least 1")

    price_id = PLAN_PRICE_IDS.get(plan)
    if not price_id:
        raise RuntimeError(f"No Stripe price ID configured for plan '{plan}'")

    import stripe as _stripe

    _stripe.api_key = _STRIPE_KEY
    metadata = {
        "org_id": org_id,
        "billing_owner_user_id": billing_owner_user_id,
        "plan": plan,
    }
    session_args: dict[str, Any] = {
        "mode": "subscription",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "line_items": [{"price": price_id, "quantity": seat_count}],
        "client_reference_id": org_id,
        "metadata": metadata,
        "subscription_data": {"metadata": metadata},
    }
    if stripe_customer_id:
        session_args["customer"] = stripe_customer_id
    else:
        session_args["customer_email"] = billing_owner_email

    session = _stripe.checkout.Session.create(**session_args)
    if not session.url:
        raise RuntimeError("Stripe Checkout did not return a redirect URL")
    return CheckoutResult(session_id=session.id, url=session.url)


def create_billing_portal_session(
    stripe_customer_id: str,
    return_url: str,
) -> BillingPortalResult:
    """Create a Stripe-hosted portal for an existing billing customer."""
    if not _STRIPE_KEY:
        raise RuntimeError("Stripe is not configured (DOCPILOT_STRIPE_SECRET_KEY missing)")

    import stripe as _stripe
    _stripe.api_key = _STRIPE_KEY

    session = _stripe.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url=return_url,
    )
    return BillingPortalResult(session_id=session.id, url=session.url)


def verify_webhook_signature(payload: bytes, sig_header: str) -> dict:
    """Verify and parse a Stripe webhook payload.

    Returns the parsed event dict.
    Raises ValueError on invalid signature.
    """
    if not _STRIPE_WEBHOOK_SECRET:
        raise RuntimeError("Stripe webhook secret not configured")

    import stripe as _stripe
    _stripe.api_key = _STRIPE_KEY

    try:
        event = _stripe.Webhook.construct_event(
            payload, sig_header, _STRIPE_WEBHOOK_SECRET
        )
    except Exception as exc:
        raise ValueError(f"Webhook signature verification failed: {exc}") from exc

    return event


def is_stripe_configured() -> bool:
    # A Checkout without signature verification would accept payment without a
    # safe entitlement reconciliation path, so partial billing config is off.
    return bool(_STRIPE_KEY and _STRIPE_WEBHOOK_SECRET and _PRO_PRICE_ID)
