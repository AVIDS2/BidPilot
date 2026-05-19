from fastapi.testclient import TestClient

from app.main import app


def test_create_project() -> None:
    client = TestClient(app)
    response = client.post(
        "/projects",
        json={"name": "Acme Bid", "scenario_package": "bidpilot"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Acme Bid"
    assert data["scenario_package"] == "bidpilot"
