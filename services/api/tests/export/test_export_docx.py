from io import BytesIO

from docx import Document
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
        v = SectionVersion(
            deliverable_section_id=section_id,
            version_number=1,
            content_markdown="## Executive Summary\n\nThis is a test summary.\n\n- Point one\n- Point two",
            created_by_actor="ai",
        )
        db.add(v)
        db.flush()
        section.status = "approved"
        section.approved_version_id = v.id
        db.commit()
    finally:
        db.close()

    response = client.get(f"/export/deliverables/{deliverable_id}/docx")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert len(response.content) > 0


def test_export_uses_reviewed_snapshot_not_newest_unapproved_draft() -> None:
    client = TestClient(app)
    project = client.post("/projects", json={"name": "Snapshot Export", "scenario_package": "bidpilot"})
    assert project.status_code == 201
    deliverable = client.post(
        "/deliverables",
        json={"project_id": project.json()["id"], "type": "proposal", "title": "Snapshot Proposal"},
    )
    assert deliverable.status_code == 201
    section = client.post(
        "/deliverables/sections",
        json={
            "deliverable_id": deliverable.json()["id"],
            "section_key": "technical",
            "title": "Technical Response",
        },
    )
    assert section.status_code == 201

    from app.db import SessionLocal
    from app.models import DeliverableSection, SectionVersion

    db = SessionLocal()
    try:
        persisted_section = db.get(DeliverableSection, section.json()["id"])
        assert persisted_section is not None
        approved = SectionVersion(
            deliverable_section_id=persisted_section.id,
            version_number=1,
            content_markdown="Approved snapshot body.",
            created_by_actor="ai",
        )
        db.add(approved)
        db.flush()
        persisted_section.status = "approved"
        persisted_section.approved_version_id = approved.id
        db.add(
            SectionVersion(
                deliverable_section_id=persisted_section.id,
                version_number=2,
                content_markdown="Unapproved candidate body.",
                created_by_actor="ai",
            )
        )
        persisted_section.status = "draft"
        db.commit()
    finally:
        db.close()

    response = client.get(f"/export/deliverables/{deliverable.json()['id']}/docx")
    assert response.status_code == 200, response.text
    document_text = "\n".join(paragraph.text for paragraph in Document(BytesIO(response.content)).paragraphs)
    assert "Approved snapshot body." in document_text
    assert "Unapproved candidate body." not in document_text
