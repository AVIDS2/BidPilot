import os
import uuid

from fastapi.testclient import TestClient

from app.main import app


def _register_payload() -> dict[str, str]:
    suffix = uuid.uuid4().hex[:8]
    return {
        "email": f"turnstile-{suffix}@docpilot.local",
        "display_name": "Turnstile User",
        "password": "Pass1234",
        "org_name": "Turnstile Org",
        "org_slug": f"turnstile-{suffix}",
    }


def test_register_rejects_missing_turnstile_token_when_enabled(monkeypatch):
    monkeypatch.setenv("DOCPILOT_TURNSTILE_SECRET_KEY", "test-secret")
    client = TestClient(app)

    response = client.post("/auth/register", json=_register_payload())

    assert response.status_code == 403
    assert response.json()["detail"] == "Human verification is required."


def test_register_accepts_successful_turnstile_token(monkeypatch):
    monkeypatch.setenv("DOCPILOT_TURNSTILE_SECRET_KEY", "test-secret")

    def fake_post(url, data, timeout):
        assert url == "https://challenges.cloudflare.com/turnstile/v0/siteverify"
        assert data["secret"] == "test-secret"
        assert data["response"] == "pass-token"

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"success": True}

        return Response()

    monkeypatch.setattr("app.security.turnstile.httpx.post", fake_post)
    client = TestClient(app)

    payload = _register_payload()
    payload["turnstile_token"] = "pass-token"
    response = client.post("/auth/register", json=payload)

    assert response.status_code == 201
    assert response.json()["email"] == payload["email"]


def test_turnstile_is_not_required_without_secret(monkeypatch):
    monkeypatch.delenv("DOCPILOT_TURNSTILE_SECRET_KEY", raising=False)
    client = TestClient(app)

    response = client.post("/auth/register", json=_register_payload())

    assert response.status_code == 201


def test_login_rejects_missing_turnstile_token_when_enabled(monkeypatch):
    monkeypatch.setenv("DOCPILOT_TURNSTILE_SECRET_KEY", "test-secret")
    client = TestClient(app)

    response = client.post(
        "/auth/login",
        json={"email": "missing-token@docpilot.local", "password": "Pass1234"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Human verification is required."


def test_password_reset_rejects_missing_turnstile_token_when_enabled(monkeypatch):
    monkeypatch.setenv("DOCPILOT_TURNSTILE_SECRET_KEY", "test-secret")
    client = TestClient(app)

    response = client.post("/auth/password-reset", json={"email": "user@example.com"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Human verification is required."
