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
    assert first_batch.successful_document_ids
    stored_first = parser.store_chunks(bundle_id, first_batch)
    assert stored_first.chunks_created == 1
    assert stored_first.parsed_assets_created == 1

    second_batch = parser.parse_bundle_documents(bundle_id)
    assert second_batch.documents == []
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
        chunk = (
            db.query(KnowledgeChunk)
            .join(SourceDocument, SourceDocument.id == KnowledgeChunk.source_document_id)
            .filter(SourceDocument.bundle_id == bundle_id)
            .one()
        )
        assert chunk.chunk_key
        assert chunk.metadata_json["locator"]["source_document_id"] == chunk.source_document_id
        assert chunk.metadata_json["locator"]["chunk_index"] == 0
    finally:
        db.close()


def test_replaying_a_parse_result_does_not_duplicate_chunks(monkeypatch) -> None:
    bundle_id, pending_storage_key = _create_bundle_with_existing_document()
    monkeypatch.setattr(
        parser,
        "_extract_text",
        lambda storage_key, _mime_type: (
            "第一章 投标要求\n投标方必须支持云平台部署。"
            if storage_key == pending_storage_key
            else ""
        ),
    )

    parsed = parser.parse_bundle_documents(bundle_id)
    first = parser.store_chunks(bundle_id, parsed)
    replay = parser.store_chunks(bundle_id, parsed)

    assert first.chunks_created == 1
    assert replay.chunks_created == 0
    assert replay.parsed_assets_created == 0

    db = SessionLocal()
    try:
        chunks = list(
            db.query(KnowledgeChunk)
            .join(SourceDocument, SourceDocument.id == KnowledgeChunk.source_document_id)
            .filter(SourceDocument.bundle_id == bundle_id)
            .all()
        )
        assert len(chunks) == 1
        document = db.get(SourceDocument, chunks[0].source_document_id)
        assert document is not None
        assert document.parse_status == "parsed"
        assert document.parse_error_code is None
    finally:
        db.close()


def test_failed_parse_is_durable_but_retryable(monkeypatch) -> None:
    bundle_id, pending_storage_key = _create_bundle_with_existing_document()
    monkeypatch.setattr(parser, "_extract_text", lambda _storage_key, _mime_type: "")

    failed_result = parser.parse_bundle_documents(bundle_id)
    stored_failure = parser.store_chunks(bundle_id, failed_result)
    assert stored_failure.failed_document_ids

    db = SessionLocal()
    try:
        document = db.query(SourceDocument).filter_by(
            bundle_id=bundle_id,
            storage_key=pending_storage_key,
        ).one()
        assert document.parse_status == "failed"
        assert document.parse_error_code == "no_extractable_text"
    finally:
        db.close()

    monkeypatch.setattr(
        parser,
        "_extract_text",
        lambda storage_key, _mime_type: "第二章 交付要求\n系统必须提供验收材料。"
        if storage_key == pending_storage_key
        else "",
    )
    retry_result = parser.parse_bundle_documents(bundle_id)
    retry_stored = parser.store_chunks(bundle_id, retry_result)

    assert retry_stored.chunks_created == 1
    db = SessionLocal()
    try:
        document = db.query(SourceDocument).filter_by(
            bundle_id=bundle_id,
            storage_key=pending_storage_key,
        ).one()
        assert document.parse_status == "parsed"
        assert document.parse_error_code is None
    finally:
        db.close()
