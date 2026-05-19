from fastapi.testclient import TestClient

from app.main import app


def test_health_contract() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
