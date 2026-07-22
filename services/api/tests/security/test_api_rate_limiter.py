from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.security.api_rate_limiter import (
    ApiRateLimitConfigurationError,
    GlobalApiRateLimitMiddleware,
    create_api_rate_limiter,
    parse_api_rate_limit,
)
from app.security.client_identity import ClientIdentityConfigurationError
from app.security.redis_rate_limiter import RateLimitExceeded, RateLimiterUnavailable


class _PermissiveLimiter:
    def check(self, key: str) -> None:
        self.key = key

    def reset(self, key: str) -> None:
        return None


class _ExceededLimiter:
    def check(self, key: str) -> None:
        raise RateLimitExceeded("fixture")

    def reset(self, key: str) -> None:
        return None


class _UnavailableLimiter:
    def check(self, key: str) -> None:
        raise RateLimiterUnavailable("fixture")

    def reset(self, key: str) -> None:
        return None


def _app_with_limiter(limiter) -> FastAPI:
    app = FastAPI()
    app.add_middleware(GlobalApiRateLimitMiddleware, limiter=limiter)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/public")
    def public() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_parse_api_rate_limit_supports_explicit_windows() -> None:
    assert parse_api_rate_limit("120/minute") == (120, 60)
    assert parse_api_rate_limit("2/hours") == (2, 3600)


@pytest.mark.parametrize("value", ["0/minute", "many/minute", "60/week", "60"])
def test_parse_api_rate_limit_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ApiRateLimitConfigurationError):
        parse_api_rate_limit(value)


def test_production_limiter_requires_explicit_trusted_proxy_configuration() -> None:
    with pytest.raises(ClientIdentityConfigurationError):
        create_api_rate_limiter(
            {
                "DOCPILOT_ENV": "production",
                "DOCPILOT_RATE_LIMIT": "100/minute",
                "DOCPILOT_REDIS_URL": "redis://:fixture-password@redis.internal:6379/0",
            }
        )


def test_production_limiter_uses_redis_and_not_memory(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_create_rate_limiter(**kwargs):
        captured.update(kwargs)
        return _PermissiveLimiter()

    monkeypatch.setattr("app.security.api_rate_limiter.create_rate_limiter", fake_create_rate_limiter)

    limiter = create_api_rate_limiter(
        {
            "DOCPILOT_ENV": "production",
            "DOCPILOT_RATE_LIMIT": "120/minute",
            "DOCPILOT_REDIS_URL": "redis://:fixture-password@redis.internal:6379/0",
            "DOCPILOT_TRUSTED_PROXY_CIDRS": "172.20.0.1/32",
        }
    )

    assert isinstance(limiter, _PermissiveLimiter)
    assert captured == {
        "redis_url": "redis://:fixture-password@redis.internal:6379/0",
        "max_attempts": 120,
        "window_seconds": 60,
        "prefix": "docpilot:rate-limit:api",
        "label": "API request",
        "require_redis": True,
    }


def test_global_limiter_returns_standard_429_without_leaking_internal_details() -> None:
    response = TestClient(_app_with_limiter(_ExceededLimiter())).get("/public")

    assert response.status_code == 429
    assert response.json() == {
        "error": "rate_limited",
        "message": "Too many requests. Please try again later.",
        "details": None,
    }


def test_global_limiter_fails_closed_with_safe_503_response() -> None:
    response = TestClient(_app_with_limiter(_UnavailableLimiter())).get("/public")

    assert response.status_code == 503
    assert response.json() == {
        "error": "rate_limit_unavailable",
        "message": "Request protection is temporarily unavailable.",
        "details": None,
    }


def test_liveness_remains_available_when_the_rate_limit_backend_is_unavailable() -> None:
    response = TestClient(_app_with_limiter(_UnavailableLimiter())).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
