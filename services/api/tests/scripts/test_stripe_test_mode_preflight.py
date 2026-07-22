from types import SimpleNamespace

import pytest

from scripts.stripe_test_mode_preflight import StripePreflightError, run_preflight


def _environment(**overrides: str) -> dict[str, str]:
    values = {
        "DOCPILOT_STRIPE_SECRET_KEY": "sk_test_preflight",
        "DOCPILOT_STRIPE_WEBHOOK_SECRET": "whsec_preflight",
        "DOCPILOT_STRIPE_PRO_PRICE_ID": "price_professional",
    }
    values.update(overrides)
    return values


def test_preflight_accepts_active_licensed_test_prices_without_writes():
    calls: list[str] = []

    class FakePrice:
        @staticmethod
        def retrieve(price_id: str):
            calls.append(price_id)
            return SimpleNamespace(
                active=True,
                recurring=SimpleNamespace(usage_type="licensed", interval="month"),
            )

    stripe = SimpleNamespace(api_key=None, Price=FakePrice)
    report = run_preflight(_environment(), stripe_module=stripe)

    assert stripe.api_key == "sk_test_preflight"
    assert calls == ["price_professional"]
    assert report == {
        "mode": "test",
        "webhook_signing_secret": "configured",
        "prices": {
            "professional": {
                "active": True,
                "recurring_interval": "month",
                "usage_type": "licensed",
            }
        },
        "result": "ready_for_manual_rehearsal",
    }


def test_preflight_rejects_a_live_mode_secret_key():
    with pytest.raises(StripePreflightError, match="Test Mode"):
        run_preflight(
            _environment(DOCPILOT_STRIPE_SECRET_KEY="sk_live_not_allowed"),
            stripe_module=SimpleNamespace(),
        )


def test_preflight_rejects_metered_prices():
    class FakePrice:
        @staticmethod
        def retrieve(_price_id: str):
            return SimpleNamespace(
                active=True,
                recurring=SimpleNamespace(usage_type="metered", interval="month"),
            )

    with pytest.raises(StripePreflightError, match="licensed"):
        run_preflight(_environment(), stripe_module=SimpleNamespace(Price=FakePrice))
