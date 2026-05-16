import uuid

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Bundle, Evidence, Project, SourceDocument


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def test_list_evidence_returns_items() -> None:
    db = SessionLocal()
    try:
        s = _uid()
        project = Project(name=f"Evidence Test {s}", slug=f"evidence-test-{s}", scenario_package="bidpilot", org_id="00000000-0000-0000-0000-000000000001")
        db.add(project)
        db.commit()
        db.refresh(project)

        bundle = Bundle(project_id=project.id, label="Evidence Bundle", source_type="upload")
        db.add(bundle)
        db.commit()
        db.refresh(bundle)

        doc = SourceDocument(
            bundle_id=bundle.id,
            storage_key="uploads/rfp.pdf",
            mime_type="application/pdf",
            checksum="def456",
            original_filename="rfp.pdf",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        ev = Evidence(
            project_id=project.id,
            source_document_id=doc.id,
            quote_text="Must comply with ISO 27001",
            confidence=0.95,
        )
        db.add(ev)
        db.commit()
        project_id = project.id
    finally:
        db.close()

    client = TestClient(app)
    resp = client.get("/evidence", params={"project_id": project_id})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["quote_text"] == "Must comply with ISO 27001"
