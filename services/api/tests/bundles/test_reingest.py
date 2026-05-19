from fastapi.testclient import TestClient

from app.main import app


def test_reingest_bundle() -> None:
    client = TestClient(app)
    proj = client.post("/projects", json={"name": "Reingest Test", "scenario_package": "bidpilot"})
    assert proj.status_code == 201
    project_id = proj.json()["id"]

    bundle = client.post("/bundles", json={"project_id": project_id, "label": "Reingest Bundle", "source_type": "upload"})
    assert bundle.status_code == 201
    bundle_id = bundle.json()["id"]

    # Reingest
    result = client.post(f"/bundles/{bundle_id}/reingest")
    assert result.status_code == 200
    assert result.json()["ingest_status"] == "queued"

    # 404 for non-existent bundle
    not_found = client.post("/bundles/nonexistent/reingest")
    assert not_found.status_code == 404

    # Verify audit event
    events = client.get(f"/audit/events?project_id={project_id}")
    assert events.status_code == 200
    assert any(e["event_type"] == "bundle.reingest" for e in events.json())
