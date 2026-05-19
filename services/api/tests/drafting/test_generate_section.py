from fastapi.testclient import TestClient

from app.main import app


def test_generate_section() -> None:
    client = TestClient(app)
    # Create a project first so the FK is satisfied
    proj = client.post(
        "/projects",
        json={"name": "Drafting Test Project", "scenario_package": "bidpilot"},
    )
    assert proj.status_code == 201
    project_id = proj.json()["id"]

    response = client.post(
        "/drafting/sections",
        json={"project_id": project_id, "section_key": "technical-approach"},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
