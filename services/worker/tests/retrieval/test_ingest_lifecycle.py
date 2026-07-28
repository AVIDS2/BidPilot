import uuid

from app.adapters import parser
from app.adapters.embedding import EmbeddingResult
from app.db import SessionLocal
from app.execution import ingest
from app.models import Bundle, KnowledgeChunk, Organization, Project, SourceDocument
from contracts import EmbeddingOutcomeStatus, MAX_DOCUMENT_PARSE_ATTEMPTS, RetrievalProfile


def _create_pending_bundle() -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        org = Organization(id=f"org-{suffix}", slug=f"lifecycle-{suffix}", name="Ingest Lifecycle")
        project = Project(
            id=f"project-{suffix}",
            org_id=org.id,
            name="Ingest Lifecycle",
            slug=f"lifecycle-{suffix}",
            scenario_package="bidpilot",
        )
        bundle = Bundle(id=f"bundle-{suffix}", project_id=project.id, label="RFP", source_type="upload")
        source = SourceDocument(
            id=f"source-{suffix}",
            bundle_id=bundle.id,
            storage_key=f"uploads/{suffix}.txt",
            mime_type="text/plain",
            checksum=suffix.ljust(64, "0"),
            original_filename="rfp.txt",
            parse_status="pending",
        )
        db.add(org)
        db.commit()
        db.add(project)
        db.commit()
        db.add(bundle)
        db.commit()
        db.add(source)
        db.commit()
        return bundle.id, source.id
    finally:
        db.close()


def _read_lifecycle_state(bundle_id: str, source_document_id: str) -> tuple[Bundle, SourceDocument, KnowledgeChunk]:
    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        document = db.get(SourceDocument, source_document_id)
        chunk = db.query(KnowledgeChunk).filter_by(source_document_id=source_document_id).one()
        assert bundle is not None
        assert document is not None
        db.expunge_all()
        return bundle, document, chunk
    finally:
        db.close()


def test_run_ingest_surfaces_unconfigured_embedding_as_partial_failure(monkeypatch) -> None:
    bundle_id, source_document_id = _create_pending_bundle()
    monkeypatch.setattr(parser, "_extract_text", lambda _key, _mime: "# RFP\n投标方必须提供部署方案。")
    monkeypatch.setattr(ingest, "get_embedding_profile", lambda: None)
    monkeypatch.setattr(ingest, "_extract_and_store_requirements", lambda *_args, **_kwargs: 0)

    result = ingest.run_ingest(bundle_id)

    assert result["status"] == "partial_failure"
    bundle, document, chunk = _read_lifecycle_state(bundle_id, source_document_id)
    assert bundle.ingest_status == "partial_failure"
    assert document.parse_status == "parsed"
    assert document.index_status == "failed"
    assert document.index_error_code == "embedding_provider_unconfigured"
    assert chunk.embedding_status == "not_configured"
    assert chunk.embedding_error_code == "embedding_provider_unconfigured"
    assert chunk.retrieval_text


def test_run_ingest_marks_document_indexed_after_successful_embedding(monkeypatch) -> None:
    bundle_id, source_document_id = _create_pending_bundle()
    profile = RetrievalProfile(
        provider="openrouter",
        model="qwen/qwen3-embedding-8b",
        dimensions=1536,
        normalizer_version="bidpilot-lexical-v1",
    )
    monkeypatch.setattr(parser, "_extract_text", lambda _key, _mime: "# RFP\n投标方必须提供部署方案。")
    monkeypatch.setattr(ingest, "get_embedding_profile", lambda: profile)
    monkeypatch.setattr(
        ingest,
        "generate_embeddings_batch",
        lambda texts: [
            EmbeddingResult(
                status=EmbeddingOutcomeStatus.SUCCESS,
                model=profile.model,
                profile_id=profile.identifier,
                vector=[0.1] * profile.dimensions,
            )
            for _ in texts
        ],
    )
    monkeypatch.setattr(ingest, "_extract_and_store_requirements", lambda *_args, **_kwargs: 0)

    result = ingest.run_ingest(bundle_id)

    assert result["status"] == "ingested"
    bundle, document, chunk = _read_lifecycle_state(bundle_id, source_document_id)
    assert bundle.ingest_status == "ingested"
    assert document.parse_status == "parsed"
    assert document.index_status == "indexed"
    assert document.index_error_code is None
    assert chunk.embedding_status == "success"
    assert chunk.embedding_profile == profile.identifier
    assert chunk.embedding is not None


def test_extract_text_reads_persisted_bucket_storage_key(monkeypatch) -> None:
    downloaded_keys: list[str] = []

    def _download_storage_key(storage_key: str) -> bytes:
        downloaded_keys.append(storage_key)
        return b"# RFP\nThe supplier must provide an implementation plan."

    monkeypatch.setattr("app.adapters.storage.download_storage_key", _download_storage_key)

    extracted = parser._extract_text(
        "docpilot-project-id/bundle-id/rfp.md",
        "text/markdown",
    )

    assert extracted.startswith("# RFP")
    assert downloaded_keys == ["docpilot-project-id/bundle-id/rfp.md"]


def test_run_ingest_stops_after_durable_parse_retry_budget(monkeypatch) -> None:
    bundle_id, source_document_id = _create_pending_bundle()
    extraction_attempts: list[str] = []

    def _no_extractable_text(storage_key: str, _mime_type: str) -> str:
        extraction_attempts.append(storage_key)
        return ""

    monkeypatch.setattr(parser, "_extract_text", _no_extractable_text)
    monkeypatch.setattr(ingest, "_extract_and_store_requirements", lambda *_args, **_kwargs: 0)

    results = [ingest.run_ingest(bundle_id) for _ in range(MAX_DOCUMENT_PARSE_ATTEMPTS + 1)]

    assert len(extraction_attempts) == MAX_DOCUMENT_PARSE_ATTEMPTS
    assert {result["status"] for result in results} == {"partial_failure"}

    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        document = db.get(SourceDocument, source_document_id)
        assert bundle is not None
        assert document is not None
        assert bundle.ingest_status == "partial_failure"
        assert document.parse_status == "failed"
        assert document.parse_attempt_count == MAX_DOCUMENT_PARSE_ATTEMPTS
        assert document.parse_error_code == "no_extractable_text"
    finally:
        db.close()
