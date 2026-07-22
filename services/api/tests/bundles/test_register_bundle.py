from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def test_register_bundle() -> None:
    client = TestClient(app)
    # Create a project first so the FK is satisfied
    proj = client.post(
        "/projects",
        json={"name": "Bundle Test Project", "scenario_package": "bidpilot"},
    )
    assert proj.status_code == 201
    project_id = proj.json()["id"]

    with patch("app.bundles.service.celery.send_task") as send_task:
        response = client.post(
            "/bundles",
            json={"project_id": project_id, "label": "RFP Pack", "source_type": "upload"},
        )

    assert response.status_code == 201
    assert response.json()["label"] == "RFP Pack"
    assert response.json()["ingest_status"] == "awaiting_upload"
    send_task.assert_not_called()
