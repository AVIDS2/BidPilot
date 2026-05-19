from fastapi.testclient import TestClient

from app.main import app


def test_runtime_summary() -> None:
    client = TestClient(app)
    response = client.get("/ops/runtime-summary")
    assert response.status_code == 200
