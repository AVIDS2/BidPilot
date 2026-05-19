from fastapi.testclient import TestClient

from app.main import app


def test_bundle_registration_creates_audit_event() -> None:
    client = TestClient(app)
    proj = client.post("/projects", json={"name": "Audit Test", "scenario_package": "bidpilot"})
    assert proj.status_code == 201
    project_id = proj.json()["id"]

    bundle = client.post("/bundles", json={"project_id": project_id, "label": "Audit Bundle", "source_type": "upload"})
    assert bundle.status_code == 201

    # Check audit events
    events = client.get(f"/audit/events?project_id={project_id}")
    assert events.status_code == 200
    event_list = events.json()
    assert any(e["event_type"] == "bundle.registered" for e in event_list)


def test_draft_request_creates_audit_event() -> None:
    client = TestClient(app)
    proj = client.post("/projects", json={"name": "Draft Audit Test", "scenario_package": "bidpilot"})
    assert proj.status_code == 201
    project_id = proj.json()["id"]

    draft = client.post("/drafting/sections", json={"project_id": project_id, "section_key": "technical-approach"})
    assert draft.status_code == 202

    events = client.get(f"/audit/events?project_id={project_id}")
    assert events.status_code == 200
    event_list = events.json()
    assert any(e["event_type"] == "draft.requested" for e in event_list)
