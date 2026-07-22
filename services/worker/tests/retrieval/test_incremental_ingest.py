import uuid

from app.adapters import parser
from app.db import SessionLocal
from app.models import Bundle, KnowledgeChunk, Organization, Project, SourceDocument


def _create_bundle_with_existing_document() -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        org = Organization(id=f"org-{suffix}", slug=f"incremental-{suffix}", name="Incremental Ingest")
        project = Project(
            id=f"project-{suffix}",
            org_id=org.id,
            name="Incremental Ingest",
            slug=f"incremental-{suffix}",
            scenario_package="bidpilot",
        )
        bundle = Bundle(id=f"bundle-{suffix}", project_id=project.id, label="Bundle", source_type="upload")
        parsed_document = SourceDocument(
            id=f"parsed-{suffix}",
            bundle_id=bundle.id,
            storage_key="uploads/already-parsed.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            checksum=f"parsed-{suffix}",
            original_filename="already-parsed.docx",
            parse_status="parsed",
        )
        pending_document = SourceDocument(
            id=f"pending-{suffix}",
            bundle_id=bundle.id,
            storage_key="uploads/new-material.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            checksum=f"pending-{suffix}",
            original_filename="new-material.docx",
            parse_status="pending",
        )
        db.add(org)
        db.commit()
        db.add(project)
        db.commit()
        db.add(bundle)
        db.commit()
        db.add_all([parsed_document, pending_document])
        db.commit()
        return bundle.id, pending_document.storage_key
    finally:
        db.close()


def test_incremental_ingest_skips_already_parsed_documents(monkeypatch) -> None:
    bundle_id, pending_storage_key = _create_bundle_with_existing_document()
    extracted_keys: list[str] = []

    def _extract_only_new_document(storage_key: str, _mime_type: str) -> str:
        extracted_keys.append(storage_key)
        return "第一章 投标要求\n投标方必须支持云平台部署。"

    monkeypatch.setattr(parser, "_extract_text", _extract_only_new_document)

    first_batch = parser.parse_bundle_documents(bundle_id)
    assert extracted_keys == [pending_storage_key]
    assert parser.store_chunks(bundle_id, first_batch) == 1

    second_batch = parser.parse_bundle_documents(bundle_id)
    assert second_batch == []
    assert extracted_keys == [pending_storage_key]

    db = SessionLocal()
    try:
        chunk_count = (
            db.query(KnowledgeChunk)
            .join(SourceDocument, SourceDocument.id == KnowledgeChunk.source_document_id)
            .filter(SourceDocument.bundle_id == bundle_id)
            .count()
        )
        assert chunk_count == 1
    finally:
        db.close()
