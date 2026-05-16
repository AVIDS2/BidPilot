"""Test PDF export endpoint."""
from fastapi.testclient import TestClient

from app.main import app


def test_export_deliverable_pdf_not_found() -> None:
    client = TestClient(app)
    response = client.get("/export/deliverables/nonexistent/pdf")
    assert response.status_code == 404


def test_export_deliverable_pdf_with_sections() -> None:
    client = TestClient(app)
    # Create project + deliverable + section + version
    proj = client.post("/projects", json={"name": "Export PDF Test", "scenario_package": "bidpilot"})
    assert proj.status_code == 201
    project_id = proj.json()["id"]

    dlv = client.post("/deliverables", json={"project_id": project_id, "type": "proposal", "title": "Test PDF Proposal"})
    assert dlv.status_code == 201
    deliverable_id = dlv.json()["id"]

    sec = client.post(
        "/deliverables/sections",
        json={"deliverable_id": deliverable_id, "section_key": "exec-summary", "title": "Executive Summary"},
    )
    assert sec.status_code == 201
    section_id = sec.json()["id"]

    # Create a version directly via DB
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
            content_markdown="# Hello PDF\n\nThis is content for the PDF export test.",
            created_by_actor="ai",
        )
        db.add(v)
        db.commit()
    finally:
        db.close()

    response = client.get(f"/export/deliverables/{deliverable_id}/pdf")
    assert response.status_code == 200
    assert "application/pdf" in response.headers.get("content-type", "")
    assert len(response.content) > 0
