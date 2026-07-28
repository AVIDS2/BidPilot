from fastapi.testclient import TestClient

from app.main import app


def test_create_and_list_requirements() -> None:
    client = TestClient(app)
    proj = client.post("/projects", json={"name": "Requirements Test", "scenario_package": "bidpilot"})
    assert proj.status_code == 201
    project_id = proj.json()["id"]

    resp = client.post(
        "/requirements",
        json={
            "project_id": project_id,
            "section_key": "technical-approach",
            "requirement_text": "Must support cloud deployment",
            "priority": "high",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["requirement_text"] == "Must support cloud deployment"
    assert data["priority"] == "high"
    assert data["status"] == "untriaged"
    assert data["bid_profile"]["coverage_status"] == "uncovered"
    assert data["bid_profile"]["evidence_status"] == "missing"

    resp = client.get("/requirements", params={"project_id": project_id})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
