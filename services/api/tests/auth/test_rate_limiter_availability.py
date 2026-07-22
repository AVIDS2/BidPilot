from fastapi.testclient import TestClient

import app.auth.router as auth_router
from app.main import app
from app.security.redis_rate_limiter import RateLimitExceeded, RateLimiterUnavailable


class _UnavailableRateLimiter:
    def check(self, _key: str) -> None:
        raise RateLimiterUnavailable("simulated redis outage")

    def reset(self, _key: str) -> None:
        return None


class _ExceededRateLimiter:
    def check(self, _key: str) -> None:
        raise RateLimitExceeded("fixture")

    def reset(self, _key: str) -> None:
        return None


def test_login_returns_503_when_required_limiter_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(auth_router, "login_rate_limiter", _UnavailableRateLimiter())
    client = TestClient(app)

    response = client.post(
        "/auth/login",
        json={"email": "rate-limited@example.com", "password": "Pass1234"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Authentication protection is temporarily unavailable."


def test_resend_returns_503_when_required_limiter_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(auth_router, "resend_rate_limiter", _UnavailableRateLimiter())
    client = TestClient(app)

    response = client.post("/auth/resend-verification?email=rate-limited@example.com")

    assert response.status_code == 503
    assert response.json()["detail"] == "Authentication protection is temporarily unavailable."


def test_register_returns_503_when_required_limiter_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(auth_router, "registration_rate_limiter", _UnavailableRateLimiter())
    client = TestClient(app)

    response = client.post(
        "/auth/register",
        json={
            "email": "rate-limit-register@example.com",
            "display_name": "Rate Limit Register",
            "password": "Pass1234",
            "org_name": "Rate Limit Org",
            "org_slug": "rate-limit-org",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Registration protection is temporarily unavailable."


def test_password_reset_returns_503_when_required_limiter_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(auth_router, "password_reset_rate_limiter", _UnavailableRateLimiter())
    client = TestClient(app)

    response = client.post("/auth/password-reset", json={"email": "rate-limit@example.com"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Password reset protection is temporarily unavailable."


def test_register_returns_429_before_human_verification_when_budget_is_exhausted(monkeypatch) -> None:
    monkeypatch.setattr(auth_router, "registration_rate_limiter", _ExceededRateLimiter())
    client = TestClient(app)

    response = client.post(
        "/auth/register",
        json={
            "email": "rate-limit-register@example.com",
            "display_name": "Rate Limit Register",
            "password": "Pass1234",
            "org_name": "Rate Limit Org",
            "org_slug": "rate-limit-org",
        },
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "Too many registration attempts. Please try again later."


def test_password_reset_returns_429_when_budget_is_exhausted(monkeypatch) -> None:
    monkeypatch.setattr(auth_router, "password_reset_rate_limiter", _ExceededRateLimiter())
    client = TestClient(app)

    response = client.post("/auth/password-reset", json={"email": "rate-limit@example.com"})

    assert response.status_code == 429
    assert response.json()["detail"] == "Too many password reset attempts. Please try again later."
