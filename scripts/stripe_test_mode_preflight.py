"""Validate BidPilot's Stripe Test Mode billing configuration without writes.

The script intentionally never prints secret values, customer data, or raw
Stripe responses. It only retrieves configured Price objects to verify that the
workspace billing adapter is attached to licensed per-seat subscription prices.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping
from typing import Any


class StripePreflightError(RuntimeError):
    """Raised when Test Mode billing configuration is not safe to rehearse."""


def _value(obj: object, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _require_test_mode_configuration(env: Mapping[str, str]) -> tuple[str, dict[str, str]]:
    secret_key = env.get("DOCPILOT_STRIPE_SECRET_KEY", "").strip()
    webhook_secret = env.get("DOCPILOT_STRIPE_WEBHOOK_SECRET", "").strip()
    professional_price_id = env.get("DOCPILOT_STRIPE_PRO_PRICE_ID", "").strip()
    enterprise_price_id = env.get("DOCPILOT_STRIPE_ENTERPRISE_PRICE_ID", "").strip()

    missing = [
        name
        for name, value in (
            ("DOCPILOT_STRIPE_SECRET_KEY", secret_key),
            ("DOCPILOT_STRIPE_WEBHOOK_SECRET", webhook_secret),
            ("DOCPILOT_STRIPE_PRO_PRICE_ID", professional_price_id),
        )
        if not value
    ]
    if missing:
        raise StripePreflightError(
            "Missing required Stripe Test Mode configuration: " + ", ".join(missing)
        )
    if not secret_key.startswith("sk_test_"):
        raise StripePreflightError(
            "Refusing to run Stripe preflight without a Stripe Test Mode secret key"
        )
    if not webhook_secret.startswith("whsec_"):
        raise StripePreflightError("Stripe webhook signing secret has an invalid format")

    prices = {"professional": professional_price_id}
    if enterprise_price_id:
        prices["enterprise"] = enterprise_price_id
    return secret_key, prices


def _validate_licensed_price(price: object, plan: str) -> dict[str, str | bool | None]:
    recurring = _value(price, "recurring")
    usage_type = _value(recurring, "usage_type")
    if not bool(_value(price, "active", False)):
        raise StripePreflightError(f"Configured {plan} price is inactive")
    if usage_type != "licensed":
        raise StripePreflightError(
            f"Configured {plan} price must use licensed recurring usage, not {usage_type!r}"
        )
    return {
        "active": True,
        "recurring_interval": _value(recurring, "interval"),
        "usage_type": usage_type,
    }


def run_preflight(
    env: Mapping[str, str] | None = None,
    *,
    stripe_module: object | None = None,
) -> dict[str, object]:
    """Perform read-only Test Mode configuration validation.

    ``stripe_module`` is injectable for offline tests. The real invocation only
    calls Stripe Price retrieval and never creates a customer, Checkout Session,
    Subscription, or webhook endpoint.
    """
    source_env = os.environ if env is None else env
    secret_key, configured_prices = _require_test_mode_configuration(source_env)

    if stripe_module is None:
        import stripe as stripe_module  # type: ignore[no-redef]

    setattr(stripe_module, "api_key", secret_key)
    price_resource = getattr(stripe_module, "Price", None)
    retrieve_price = getattr(price_resource, "retrieve", None)
    if not callable(retrieve_price):
        raise StripePreflightError("Installed Stripe SDK does not expose Price.retrieve")

    validated_prices: dict[str, dict[str, str | bool | None]] = {}
    for plan, price_id in configured_prices.items():
        try:
            price = retrieve_price(price_id)
        except Exception as exc:  # Stripe SDK errors intentionally remain redacted.
            raise StripePreflightError(f"Could not retrieve configured {plan} price") from exc
        validated_prices[plan] = _validate_licensed_price(price, plan)

    return {
        "mode": "test",
        "webhook_signing_secret": "configured",
        "prices": validated_prices,
        "result": "ready_for_manual_rehearsal",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Stripe Test Mode price and webhook configuration for BidPilot."
    )
    parser.parse_args()
    try:
        report = run_preflight()
    except StripePreflightError as exc:
        print(json.dumps({"result": "not_ready", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
