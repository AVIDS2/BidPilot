from fastapi.testclient import TestClient

from app.main import app


def test_update_requirement() -> None:
    client = TestClient(app)
    proj = client.post("/projects", json={"name": "Req Update Test", "scenario_package": "bidpilot"})
    assert proj.status_code == 201
    project_id = proj.json()["id"]

    # Create a requirement
    req = client.post("/requirements", json={"project_id": project_id, "section_key": "scope", "requirement_text": "System shall authenticate users", "priority": "high"})
    assert req.status_code == 201
    req_id = req.json()["id"]

    # Update it
    updated = client.put(f"/requirements/{req_id}", json={"requirement_text": "System shall authenticate users via SSO", "status": "confirmed"})
    assert updated.status_code == 200
    assert updated.json()["requirement_text"] == "System shall authenticate users via SSO"
    assert updated.json()["status"] == "confirmed"

    # Verify audit event
    events = client.get(f"/audit/events?project_id={project_id}")
    assert events.status_code == 200
    assert any(e["event_type"] == "requirement.updated" for e in events.json())
