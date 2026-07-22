from fastapi.testclient import TestClient

from app.main import app


def test_list_audit_events() -> None:
    client = TestClient(app)
    created = client.post(
        "/projects",
        json={"name": "Audit List Project", "scenario_package": "bidpilot"},
    )
    assert created.status_code == 201

    response = client.get("/audit/events", params={"project_id": created.json()["id"]})
    assert response.status_code == 200
    assert isinstance(response.json(), list)
