from fastapi.testclient import TestClient

from app.main import app


def test_export_deliverable_docx_not_found() -> None:
    client = TestClient(app)
    response = client.get("/export/deliverables/nonexistent-id/docx")
    assert response.status_code == 404


def test_export_deliverable_docx_with_sections() -> None:
    client = TestClient(app)
    # Create project + deliverable + section + version
    proj = client.post("/projects", json={"name": "Export Test", "scenario_package": "bidpilot"})
    assert proj.status_code == 201
    project_id = proj.json()["id"]

    dlv = client.post("/deliverables", json={"project_id": project_id, "type": "proposal", "title": "Test Proposal"})
    assert dlv.status_code == 201
    deliverable_id = dlv.json()["id"]

    sec = client.post(
        "/deliverables/sections",
        json={"deliverable_id": deliverable_id, "section_key": "exec-summary", "title": "Executive Summary"},
    )
    assert sec.status_code == 201
    section_id = sec.json()["id"]

    # Create a version via the drafting endpoint (which creates a run, but we need a version directly)
    # Use the versions endpoint if available, or create via DB
    from app.db import SessionLocal
    from app.models import DeliverableSection, SectionVersion
    db = SessionLocal()
    try:
        section = db.get(DeliverableSection, section_id)
        assert section is not None
        section.status = "approved"
        v = SectionVersion(
            deliverable_section_id=section_id,
            version_number=1,
            content_markdown="## Executive Summary\n\nThis is a test summary.\n\n- Point one\n- Point two",
            created_by_actor="ai",
        )
        db.add(v)
        db.commit()
    finally:
        db.close()

    response = client.get(f"/export/deliverables/{deliverable_id}/docx")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert len(response.content) > 0
