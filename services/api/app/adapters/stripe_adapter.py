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


def create_checkout_session(
    user_id: str,
    user_email: str,
    plan: str,
    success_url: str,
    cancel_url: str,
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

    session = _stripe.checkout.Session.create(
        mode="subscription",
        success_url=success_url,
        cancel_url=cancel_url,
        line_items=[{"price": price_id, "quantity": 1}],
        customer_email=user_email,
        metadata={"user_id": user_id, "plan": plan},
    )
    return CheckoutResult(session_id=session.id, url=session.url)


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
    return bool(_STRIPE_KEY)
