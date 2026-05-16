import uuid

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Bundle, KnowledgeChunk, Project, SourceDocument


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def test_search_returns_matching_chunks() -> None:
    db = SessionLocal()
    try:
        s = _uid()
        project = Project(name=f"Search Test {s}", slug=f"search-test-{s}", scenario_package="bidpilot", org_id="00000000-0000-0000-0000-000000000001")
        db.add(project)
        db.commit()
        db.refresh(project)

        bundle = Bundle(project_id=project.id, label="Test Bundle", source_type="upload")
        db.add(bundle)
        db.commit()
        db.refresh(bundle)

        doc = SourceDocument(
            bundle_id=bundle.id,
            storage_key="uploads/test.pdf",
            mime_type="application/pdf",
            checksum="abc123",
            original_filename="test.pdf",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        chunk = KnowledgeChunk(
            project_id=project.id,
            source_document_id=doc.id,
            chunk_index=0,
            content="The system must support cloud deployment on AWS",
        )
        db.add(chunk)
        db.commit()
        project_id = project.id
    finally:
        db.close()

    client = TestClient(app)
    resp = client.post(
        "/retrieval/search",
        json={"project_id": project_id, "query": "cloud deployment", "top_k": 5},
    )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    assert "cloud deployment" in results[0]["content"].lower()


def test_search_returns_empty_for_no_match() -> None:
    db = SessionLocal()
    try:
        s = _uid()
        project = Project(name=f"Empty Search {s}", slug=f"empty-search-{s}", scenario_package="bidpilot", org_id="00000000-0000-0000-0000-000000000001")
        db.add(project)
        db.commit()
        db.refresh(project)
        project_id = project.id
    finally:
        db.close()

    client = TestClient(app)
    resp = client.post(
        "/retrieval/search",
        json={"project_id": project_id, "query": "nonexistent topic", "top_k": 5},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 0
