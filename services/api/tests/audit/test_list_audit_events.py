from fastapi.testclient import TestClient

from app.main import app


def test_list_audit_events() -> None:
    client = TestClient(app)
    response = client.get("/audit/events", params={"project_id": "p1"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)
