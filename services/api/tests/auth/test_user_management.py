"""Tests for password change, password reset, admin user management, email verification, refresh tokens, and account deletion."""

import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

STRONG_PW = "Secret123"


def _register_and_login(email: str | None = None) -> tuple[str, str]:
    """Register a user, verify email, and return (email, token)."""
    if email is None:
        email = f"user-{uuid.uuid4().hex[:8]}@docpilot.local"
    reg = client.post("/auth/register", json={"email": email, "display_name": "Test User", "password": STRONG_PW})
    user_id = reg.json().get("id")
    # Auto-verify email so login succeeds
    if user_id:
        client.post(f"/auth/users/{user_id}/verify")
    resp = client.post("/auth/login", json={"email": email, "password": STRONG_PW})
    token = resp.json()["access_token"]
    return email, token


def _admin_token() -> str:
    """Get an admin token using dev fallback."""
    resp = client.get("/auth/me")
    return ""  # dev mode doesn't need token


# --- Password change ---

def test_change_password_success():
    email, token = _register_and_login()
    resp = client.patch(
        "/auth/me",
        json={"current_password": STRONG_PW, "new_password": "NewPass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # Login with new password
    resp = client.post("/auth/login", json={"email": email, "password": "NewPass456"})
    assert resp.status_code == 200


def test_change_password_wrong_current():
    _, token = _register_and_login()
    resp = client.patch(
        "/auth/me",
        json={"current_password": "WrongPass1", "new_password": "NewPass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "incorrect" in resp.json()["detail"].lower()


def test_change_password_missing_current():
    _, token = _register_and_login()
    resp = client.patch(
        "/auth/me",
        json={"new_password": "NewPass456"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "current password is required" in resp.json()["detail"].lower()


def test_change_password_weak_new():
    _, token = _register_and_login()
    resp = client.patch(
        "/auth/me",
        json={"current_password": STRONG_PW, "new_password": "weak"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "8 characters" in resp.json()["detail"]


# --- Password strength on registration ---

def test_register_weak_password_no_uppercase():
    email = f"weak-{uuid.uuid4().hex[:8]}@docpilot.local"
    resp = client.post("/auth/register", json={"email": email, "display_name": "Weak", "password": "secret123"})
    assert resp.status_code == 400
    assert "uppercase" in resp.json()["detail"].lower()


def test_register_weak_password_no_digit():
    email = f"weak-{uuid.uuid4().hex[:8]}@docpilot.local"
    resp = client.post("/auth/register", json={"email": email, "display_name": "Weak", "password": "Secretabc"})
    assert resp.status_code == 400
    assert "digit" in resp.json()["detail"].lower()


def test_register_weak_password_too_short():
    email = f"weak-{uuid.uuid4().hex[:8]}@docpilot.local"
    resp = client.post("/auth/register", json={"email": email, "display_name": "Weak", "password": "Sec1"})
    assert resp.status_code == 400
    assert "8 characters" in resp.json()["detail"]


# --- Password reset ---

def test_password_reset_request_returns_success_even_for_unknown_email():
    resp = client.post("/auth/password-reset", json={"email": "nonexistent@test.com"})
    assert resp.status_code == 200
    assert "reset link" in resp.json()["message"].lower()


def test_password_reset_confirm_invalid_token():
    resp = client.post("/auth/password-reset/confirm", json={"token": "invalid-token", "new_password": "NewPass456"})
    assert resp.status_code == 400


# --- Admin user management ---

def _get_users_list():
    """Get the flat list of users from the paginated admin endpoint."""
    resp = client.get("/auth/users?page_size=100")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    return data["items"]

def test_admin_can_list_users():
    # In dev mode, auth is not required; admin endpoints use dev fallback
    users = _get_users_list()
    assert isinstance(users, list)


def test_admin_can_update_user_role():
    # Register a member user first
    email, _ = _register_and_login()
    # Get user list to find the user id
    users = _get_users_list()
    user_id = next(u["id"] for u in users if u["email"] == email)
    assert user_id is not None

    # Update role to admin
    resp = client.patch(f"/auth/users/{user_id}/role?role=admin")
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


def test_admin_update_role_invalid():
    resp = client.patch("/auth/users/some-id/role?role=superuser")
    assert resp.status_code == 400


def test_admin_can_disable_user():
    email, _ = _register_and_login()
    users = _get_users_list()
    user_id = next(u["id"] for u in users if u["email"] == email)

    resp = client.patch(f"/auth/users/{user_id}/status?disabled=true")
    assert resp.status_code == 200

    # Disabled user cannot login
    resp = client.post("/auth/login", json={"email": email, "password": STRONG_PW})
    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"].lower()


def test_admin_can_re_enable_user():
    email, _ = _register_and_login()
    users = _get_users_list()
    user_id = next(u["id"] for u in users if u["email"] == email)

    # Disable
    client.patch(f"/auth/users/{user_id}/status?disabled=true")
    # Re-enable
    resp = client.patch(f"/auth/users/{user_id}/status?disabled=false")
    assert resp.status_code == 200

    # Can login again
    resp = client.post("/auth/login", json={"email": email, "password": STRONG_PW})
    assert resp.status_code == 200


# --- Login rate limiting ---

def test_login_rate_limited_after_5_failures():
    email, _ = _register_and_login()
    for _ in range(5):
        client.post("/auth/login", json={"email": email, "password": "WrongPass1"})
    resp = client.post("/auth/login", json={"email": email, "password": "WrongPass1"})
    assert resp.status_code == 429
    assert "too many" in resp.json()["detail"].lower()


# --- Email verification ---

def test_register_returns_email_verified_false():
    email = f"verify-{uuid.uuid4().hex[:8]}@docpilot.local"
    resp = client.post("/auth/register", json={"email": email, "display_name": "Verify User", "password": STRONG_PW})
    assert resp.status_code == 201
    assert resp.json()["email_verified"] is False


def test_verify_email_endpoint():
    email = f"verify-{uuid.uuid4().hex[:8]}@docpilot.local"
    client.post("/auth/register", json={"email": email, "display_name": "Verify User", "password": STRONG_PW})
    # In dev mode, token is logged to console. We create one directly for testing.
    from app.auth.service import create_email_verification_token
    from app.db import get_db
    from app.models import User
    db = next(get_db())
    user = db.query(User).filter_by(email=email).first()
    token = create_email_verification_token(db, user.id)
    resp = client.post(f"/auth/verify-email?token={token}")
    assert resp.status_code == 200
    assert "verified" in resp.json()["message"].lower()


def test_resend_verification_requires_email_or_auth():
    resp = client.post("/auth/resend-verification")
    assert resp.status_code == 400


# --- Refresh token ---

def test_login_returns_refresh_token():
    email, _ = _register_and_login()
    resp = client.post("/auth/login", json={"email": email, "password": STRONG_PW})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["refresh_token"] is not None


def test_refresh_token_works():
    email, _ = _register_and_login()
    resp = client.post("/auth/login", json={"email": email, "password": STRONG_PW})
    refresh_token = resp.json()["refresh_token"]
    resp = client.post(f"/auth/refresh?refresh_token={refresh_token}")
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # New access token should work
    me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == email


def test_refresh_token_rejected_for_disabled_user():
    # Bootstrap admin
    from app.auth.service import bootstrap_admin_command
    from app.db import get_db
    db = next(get_db())
    admin_result = bootstrap_admin_command(db, f"admin-{uuid.uuid4().hex[:8]}@docpilot.local", "Admin", STRONG_PW)
    admin_token_resp = client.post("/auth/login", json={"email": admin_result.user.email, "password": STRONG_PW})
    admin_token = admin_token_resp.json()["access_token"]

    # Register regular user and verify email
    email = f"refresh-{uuid.uuid4().hex[:8]}@docpilot.local"
    reg = client.post("/auth/register", json={"email": email, "display_name": "Refresh User", "password": STRONG_PW})
    user_id = reg.json().get("id")
    client.post(f"/auth/users/{user_id}/verify")

    resp = client.post("/auth/login", json={"email": email, "password": STRONG_PW})
    refresh_token = resp.json()["refresh_token"]

    # Disable user
    client.patch(f"/auth/users/{user_id}/status?disabled=true", headers={"Authorization": f"Bearer {admin_token}"})

    # Refresh should fail
    resp = client.post(f"/auth/refresh?refresh_token={refresh_token}")
    assert resp.status_code == 401


# --- Account deletion ---

def test_delete_account():
    email, token = _register_and_login()
    resp = client.delete("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    # Can no longer get /me
    me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 401


def test_delete_account_requires_auth():
    resp = client.delete("/auth/me")
    assert resp.status_code == 401


# --- Data export ---

def test_export_user_data():
    email, token = _register_and_login()
    resp = client.get("/auth/me/export", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "account" in data
    assert data["account"][0]["email"] == email


def test_export_requires_auth():
    resp = client.get("/auth/me/export")
    assert resp.status_code == 401
