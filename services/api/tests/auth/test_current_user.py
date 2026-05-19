import uuid

from fastapi.testclient import TestClient

from app.main import app


def test_current_user_dev_fallback() -> None:
    client = TestClient(app)
    response = client.get("/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "dev-user"
    assert data["role"] == "admin"


def test_register_login_me_flow() -> None:
    client = TestClient(app)
    email = f"test-{uuid.uuid4().hex[:8]}@docpilot.local"

    # Register
    resp = client.post(
        "/auth/register",
        json={"email": email, "display_name": "Test User", "password": "Secret123"},
    )
    assert resp.status_code == 201
    user_id = resp.json()["id"]

    # Verify email (required before login)
    resp = client.post(f"/auth/users/{user_id}/verify")
    assert resp.status_code == 200

    # Login
    resp = client.post(
        "/auth/login",
        json={"email": email, "password": "Secret123"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Me with token
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == email
