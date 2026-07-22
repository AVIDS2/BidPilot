"""Production auth mode must never surface the local development identity."""

from unittest.mock import patch


def test_current_user_requires_token_when_production_auth_is_enabled(client):
    with patch("app.auth.router.AUTH_REQUIRED", True):
        response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_subscription_requires_token_when_production_auth_is_enabled(client):
    with patch("app.auth.router.AUTH_REQUIRED", True):
        response = client.get("/auth/subscription")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_development_mode_preserves_local_identity_fallback(client):
    with patch("app.auth.router.AUTH_REQUIRED", False):
        response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["id"] == "dev-user"
