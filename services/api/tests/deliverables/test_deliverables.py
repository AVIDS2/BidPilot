from fastapi.testclient import TestClient

from app.main import app


def test_create_and_list_deliverable() -> None:
    client = TestClient(app)
    # Create a project first
    proj = client.post("/projects", json={"name": "Deliverable Test", "scenario_package": "bidpilot"})
    assert proj.status_code == 201
    project_id = proj.json()["id"]

    # Create a deliverable
    resp = client.post(
        "/deliverables",
        json={"project_id": project_id, "type": "proposal", "title": "Technical Proposal"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Technical Proposal"
    assert data["status"] == "draft"
    deliverable_id = data["id"]

    # List deliverables by project
    resp = client.get("/deliverables", params={"project_id": project_id})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    # Create a section
    resp = client.post(
        "/deliverables/sections",
        json={"deliverable_id": deliverable_id, "section_key": "exec-summary", "title": "Executive Summary"},
    )
    assert resp.status_code == 201
    assert resp.json()["section_key"] == "exec-summary"

    # List sections
    resp = client.get(f"/deliverables/{deliverable_id}/sections")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
