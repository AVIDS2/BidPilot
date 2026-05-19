from fastapi.testclient import TestClient

from app.main import app


def test_list_execution_runs() -> None:
    client = TestClient(app)
    # Create a project and trigger a drafting run
    proj = client.post("/projects", json={"name": "Execution Test", "scenario_package": "bidpilot"})
    assert proj.status_code == 201
    project_id = proj.json()["id"]

    draft = client.post("/drafting/sections", json={"project_id": project_id, "section_key": "approach"})
    assert draft.status_code == 202
    run_id = draft.json()["run_id"]

    # Query the run
    resp = client.get(f"/execution/runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"

    # List runs by project
    resp = client.get("/execution/runs", params={"project_id": project_id})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
