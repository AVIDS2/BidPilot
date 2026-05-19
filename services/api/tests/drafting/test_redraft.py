from fastapi.testclient import TestClient

from app.main import app


def test_redraft_section_with_feedback() -> None:
    client = TestClient(app)
    proj = client.post("/projects", json={"name": "Redraft Test", "scenario_package": "bidpilot"})
    assert proj.status_code == 201
    project_id = proj.json()["id"]

    # Redraft with review feedback
    redraft = client.post("/drafting/sections/redraft", json={"project_id": project_id, "section_key": "technical-approach", "review_feedback": "Add more detail on architecture"})
    assert redraft.status_code == 202
    assert redraft.json()["status"] == "queued"

    # Verify audit event
    events = client.get(f"/audit/events?project_id={project_id}")
    assert events.status_code == 200
    assert any(e["event_type"] == "draft.redraft" for e in events.json())
