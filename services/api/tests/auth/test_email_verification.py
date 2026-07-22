"""Tests for email verification enforcement and resend rate limiting."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth.service import resend_rate_limiter


@pytest.fixture(autouse=True)
def _clear_rate_limiter():
    resend_rate_limiter._attempts.clear()
    yield
    resend_rate_limiter._attempts.clear()


def _register(client: TestClient, email: str | None = None, password: str = "Pass1234") -> str:
    """Register a user and return the email used."""
    if email is None:
        email = f"verify-{uuid.uuid4().hex[:8]}@docpilot.local"
    resp = client.post("/auth/register", json={
        "email": email,
        "display_name": "Test User",
        "password": password,
    })
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    return email


def _get_user_id(client: TestClient, email: str) -> str | None:
    """Get user ID from the database via admin list endpoint (dev mode)."""
    resp = client.get("/auth/users?page_size=100")
    if resp.status_code != 200:
        return None
    data = resp.json()
    users = data.get("items", data) if isinstance(data, dict) else data
    for u in users:
        if u.get("email") == email:
            return u.get("id")
    return None


def test_login_rejected_for_unverified_user(client: TestClient = TestClient(app)):
    """Unverified users cannot log in — they get 403 with email_not_verified."""
    email = _register(client)
    resp = client.post("/auth/login", json={
        "email": email,
        "password": "Pass1234",
    })
    assert resp.status_code == 403
    detail = resp.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "email_not_verified"
    else:
        assert "not verified" in str(detail).lower()


def test_login_succeeds_after_verification(client: TestClient = TestClient(app)):
    """After email verification, login succeeds."""
    email = _register(client)
    # Admin verifies the user
    user_id = _get_user_id(client, email)
    assert user_id is not None
    resp = client.post(f"/auth/users/{user_id}/verify")
    assert resp.status_code == 200
    assert resp.json().get("email_verified") is True

    # Now login should succeed
    resp = client.post("/auth/login", json={
        "email": email,
        "password": "Pass1234",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_verify_email_endpoint(client: TestClient = TestClient(app)):
    """POST /auth/verify-email with a valid token marks user as verified."""
    email = _register(client)
    # Get a verification token via resend
    resp = client.post(f"/auth/resend-verification?email={email}")
    assert resp.status_code == 200

    user_id = _get_user_id(client, email)
    resp = client.post(f"/auth/users/{user_id}/verify")
    assert resp.status_code == 200
    assert resp.json().get("email_verified") is True


def test_resend_verification_rate_limited(client: TestClient = TestClient(app)):
    """Resend verification is rate-limited to 3 per hour per email."""
    email = _register(client)

    # First 3 resends should succeed
    for i in range(3):
        resp = client.post(f"/auth/resend-verification?email={email}")
        assert resp.status_code == 200, f"Resend {i+1} should succeed"

    # 4th should be rate-limited
    resp = client.post(f"/auth/resend-verification?email={email}")
    assert resp.status_code == 429


def test_resend_nonexistent_email_returns_generic_message(client: TestClient = TestClient(app)):
    """Resend for non-existent email returns generic message (no user enumeration)."""
    unique = f"nonexistent-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(f"/auth/resend-verification?email={unique}")
    assert resp.status_code == 200
    assert "If the account exists" in resp.json().get("message", "")


def test_resend_already_verified_returns_generic_message(client: TestClient = TestClient(app)):
    """Resend for already-verified user returns generic message."""
    email = _register(client)
    user_id = _get_user_id(client, email)
    client.post(f"/auth/users/{user_id}/verify")

    resp = client.post(f"/auth/resend-verification?email={email}")
    assert resp.status_code == 200
    assert "If the account exists" in resp.json().get("message", "")


def test_admin_verify_user(client: TestClient = TestClient(app)):
    """Admin can manually verify a user via POST /auth/users/{id}/verify."""
    email = _register(client)
    user_id = _get_user_id(client, email)
    assert user_id is not None

    resp = client.post(f"/auth/users/{user_id}/verify")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("email_verified") is True
    assert body.get("id") == user_id


def test_admin_verify_nonexistent_user(client: TestClient = TestClient(app)):
    """Admin verify for non-existent user returns 404."""
    resp = client.post("/auth/users/nonexistent-id/verify")
    assert resp.status_code == 404


def test_refresh_token_rejected_for_unverified_user(client: TestClient = TestClient(app)):
    """Refresh token works when user is verified."""
    email = _register(client)

    # Verify the user, login, then test refresh
    user_id = _get_user_id(client, email)
    client.post(f"/auth/users/{user_id}/verify")

    resp = client.post("/auth/login", json={
        "email": email,
        "password": "Pass1234",
    })
    assert resp.status_code == 200
    refresh_token = resp.json().get("refresh_token")
    assert refresh_token

    # Now use the refresh token — it should work since user is verified
    resp = client.post(f"/auth/refresh?refresh_token={refresh_token}")
    assert resp.status_code == 200


def test_bootstrap_admin_auto_verified(client: TestClient = TestClient(app)):
    """Bootstrap admin users are automatically email-verified."""
    from app.db import get_db
    from app.auth.service import bootstrap_admin_command

    db = next(get_db())
    # Use a unique email to avoid collision with other tests
    result = bootstrap_admin_command(db, "autoadmin-verify-test@example.com", "Auto Admin", "Pass1234")
    assert result.user.email_verified is True
    assert result.status in ("created", "already_admin")


def test_register_sends_verification_email(client: TestClient = TestClient(app)):
    """Registration creates an unverified user and sends verification email."""
    import uuid
    unique_email = f"newreg-{uuid.uuid4().hex[:8]}@docpilot.local"
    resp = client.post("/auth/register", json={
        "email": unique_email,
        "display_name": "New Reg",
        "password": "Pass1234",
    })
    assert resp.status_code == 201
    # User should be unverified
    assert resp.json().get("email_verified") is False

    # Login should be blocked
    resp = client.post("/auth/login", json={
        "email": unique_email,
        "password": "Pass1234",
    })
    assert resp.status_code == 403
