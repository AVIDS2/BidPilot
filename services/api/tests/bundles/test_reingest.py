from unittest.mock import patch

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import KnowledgeChunk, SourceDocument


def test_reingest_bundle() -> None:
    client = TestClient(app)
    proj = client.post("/projects", json={"name": "Reingest Test", "scenario_package": "bidpilot"})
    assert proj.status_code == 201
    project_id = proj.json()["id"]

    bundle = client.post("/bundles", json={"project_id": project_id, "label": "Reingest Bundle", "source_type": "upload"})
    assert bundle.status_code == 201
    bundle_id = bundle.json()["id"]

    empty_result = client.post(f"/bundles/{bundle_id}/reingest")
    assert empty_result.status_code == 409

    db = SessionLocal()
    try:
        db.add(
            SourceDocument(
                bundle_id=bundle_id,
                storage_key="uploads/reingest.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                checksum="reingest-test",
                original_filename="reingest.docx",
                parse_status="pending",
            )
        )
        db.commit()
    finally:
        db.close()

    # Process newly uploaded material.
    with patch("app.bundles.service.celery.send_task") as send_task:
        result = client.post(f"/bundles/{bundle_id}/reingest")

    assert result.status_code == 200
    assert result.json()["ingest_status"] == "queued"
    send_task.assert_called_once_with("worker.ingest_bundle", args=[bundle_id])

    # 404 for non-existent bundle
    not_found = client.post("/bundles/nonexistent/reingest")
    assert not_found.status_code == 404

    # Verify audit event
    events = client.get(f"/audit/events?project_id={project_id}")
    assert events.status_code == 200
    assert any(e["event_type"] == "bundle.reingest" for e in events.json())


def test_reindex_bundle_dispatches_dedicated_task_without_reparsing() -> None:
    client = TestClient(app)
    project = client.post("/projects", json={"name": "Reindex Test", "scenario_package": "bidpilot"})
    assert project.status_code == 201
    project_id = project.json()["id"]

    bundle = client.post("/bundles", json={"project_id": project_id, "label": "Reindex Bundle", "source_type": "upload"})
    assert bundle.status_code == 201
    bundle_id = bundle.json()["id"]

    db = SessionLocal()
    try:
        source = SourceDocument(
            bundle_id=bundle_id,
            storage_key="uploads/reindex.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            checksum="reindex-test",
            original_filename="reindex.docx",
            parse_status="parsed",
        )
        db.add(source)
        db.flush()
        db.add(
            KnowledgeChunk(
                project_id=project_id,
                source_document_id=source.id,
                chunk_index=0,
                content="现有资料块只能重新向量化，不能重复解析。",
            )
        )
        db.commit()
    finally:
        db.close()

    with patch("app.bundles.service.celery.send_task") as send_task:
        response = client.post(f"/bundles/{bundle_id}/reindex")

    assert response.status_code == 200
    assert response.json()["ingest_status"] == "queued"
    send_task.assert_called_once_with("worker.reindex_bundle", args=[bundle_id])

    events = client.get(f"/audit/events?project_id={project_id}")
    assert events.status_code == 200
    assert any(event["event_type"] == "bundle.reindex_requested" for event in events.json())
