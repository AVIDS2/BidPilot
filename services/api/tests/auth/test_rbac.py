import uuid

from fastapi.testclient import TestClient

from app.main import app


def _member_token(client: TestClient) -> str:
    email = f"member-{uuid.uuid4().hex[:8]}@docpilot.local"
    password = "Secret123"
    response = client.post(
        "/auth/register",
        json={"email": email, "display_name": "Member User", "password": password},
    )
    assert response.status_code == 201
    user_id = response.json().get("id")

    # Verify email before login
    client.post(f"/auth/users/{user_id}/verify")

    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return str(response.json()["access_token"])


def test_member_cannot_access_audit_events() -> None:
    client = TestClient(app)
    token = _member_token(client)

    response = client.get(
        "/audit/events",
        params={"project_id": "p1"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin role required"


def test_member_cannot_access_ops_runtime_summary() -> None:
    client = TestClient(app)
    token = _member_token(client)

    response = client.get(
        "/ops/runtime-summary",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin role required"
