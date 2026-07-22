import uuid

import pytest

from app.adapters.embedding import EmbeddingResult
from app.db import SessionLocal
from app.execution.ingest import _embed_and_update_chunks
from app.models import Bundle, KnowledgeChunk, ModelUsageRecord, Organization, Project, SourceDocument
from contracts import EmbeddingOutcomeStatus, RetrievalProfile


def _create_chunk() -> str:
    suffix = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        org = Organization(id=f"org-{suffix}", slug=f"retrieval-{suffix}", name="Retrieval Test")
        project = Project(
            id=f"project-{suffix}",
            org_id=org.id,
            name="Retrieval Test",
            slug=f"retrieval-{suffix}",
            scenario_package="bidpilot",
        )
        bundle = Bundle(id=f"bundle-{suffix}", project_id=project.id, label="Bundle", source_type="upload")
        source = SourceDocument(
            id=f"source-{suffix}",
            bundle_id=bundle.id,
            storage_key="uploads/retrieval.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            checksum=suffix,
            original_filename="retrieval.docx",
        )
        chunk = KnowledgeChunk(
            id=f"chunk-{suffix}",
            project_id=project.id,
            source_document_id=source.id,
            chunk_index=0,
            content="投标文件必须支持云平台部署。",
        )
        db.add(org)
        db.commit()
        db.add(project)
        db.commit()
        db.add(bundle)
        db.commit()
        db.add(source)
        db.commit()
        db.add(chunk)
        db.commit()
        return bundle.id
    finally:
        db.close()


def _read_chunk(bundle_id: str) -> KnowledgeChunk:
    db = SessionLocal()
    try:
        chunk = (
            db.query(KnowledgeChunk)
            .join(SourceDocument)
            .filter(SourceDocument.bundle_id == bundle_id)
            .one()
        )
        db.expunge(chunk)
        return chunk
    finally:
        db.close()


def _update_chunk_embedding(
    bundle_id: str,
    *,
    vector: list[float] | None,
    profile_id: str | None,
    status: str,
) -> None:
    db = SessionLocal()
    try:
        chunk = (
            db.query(KnowledgeChunk)
            .join(SourceDocument)
            .filter(SourceDocument.bundle_id == bundle_id)
            .one()
        )
        chunk.embedding = vector
        chunk.embedding_profile = profile_id
        chunk.embedding_status = status
        db.commit()
    finally:
        db.close()


def _active_profile_id() -> str:
    return RetrievalProfile(
        provider="legacy",
        model="text-embedding-3-small",
        dimensions=1536,
        normalizer_version="bidpilot-lexical-v1",
    ).identifier


def test_failed_embedding_keeps_sparse_text_without_persisting_a_vector(monkeypatch) -> None:
    bundle_id = _create_chunk()
    failed = EmbeddingResult(
        status=EmbeddingOutcomeStatus.TRANSIENT_FAILURE,
        model="qwen/qwen3-embedding-8b",
        error_code="provider_timeout",
        profile_id="openrouter:qwen/qwen3-embedding-8b:1536:bidpilot-lexical-v1",
    )
    monkeypatch.setattr("app.execution.ingest.generate_embeddings_batch", lambda _texts: [failed])

    assert _embed_and_update_chunks(bundle_id) == 0

    chunk = _read_chunk(bundle_id)
    assert chunk.embedding is None
    assert chunk.embedding_profile is None
    assert chunk.embedding_status == "transient_failure"
    assert chunk.embedding_error_code == "provider_timeout"
    assert "云平" in chunk.retrieval_text.split()


def test_successful_embedding_persists_profile_and_vector(monkeypatch) -> None:
    bundle_id = _create_chunk()
    profile_id = "openrouter:qwen/qwen3-embedding-8b:1536:bidpilot-lexical-v1"
    success = EmbeddingResult(
        status=EmbeddingOutcomeStatus.SUCCESS,
        model="qwen/qwen3-embedding-8b",
        profile_id=profile_id,
        vector=[0.1] * 1536,
    )
    monkeypatch.setattr("app.execution.ingest.generate_embeddings_batch", lambda _texts: [success])

    assert _embed_and_update_chunks(bundle_id) == 1

    chunk = _read_chunk(bundle_id)
    assert chunk.embedding is not None
    assert len(chunk.embedding) == 1536
    assert chunk.embedding_profile == profile_id
    assert chunk.embedding_status == "success"
    assert chunk.embedding_error_code is None


def test_current_successful_chunk_is_not_embedded_again(monkeypatch) -> None:
    bundle_id = _create_chunk()
    profile_id = _active_profile_id()
    _update_chunk_embedding(
        bundle_id,
        vector=[0.1] * 1536,
        profile_id=profile_id,
        status="success",
    )
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    calls: list[list[str]] = []

    def _unexpected_provider_call(texts: list[str]):
        calls.append(texts)
        return []

    monkeypatch.setattr("app.execution.ingest.generate_embeddings_batch", _unexpected_provider_call)

    assert _embed_and_update_chunks(bundle_id) == 0
    assert calls == []

    chunk = _read_chunk(bundle_id)
    assert chunk.embedding_profile == profile_id
    assert chunk.embedding_status == "success"
    assert chunk.embedding is not None


def test_failed_profile_refresh_keeps_previous_vector(monkeypatch) -> None:
    bundle_id = _create_chunk()
    previous_vector = [0.2] * 1536
    previous_profile = "legacy:previous-model:1536:bidpilot-lexical-v1"
    _update_chunk_embedding(
        bundle_id,
        vector=previous_vector,
        profile_id=previous_profile,
        status="success",
    )
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    failed = EmbeddingResult(
        status=EmbeddingOutcomeStatus.TRANSIENT_FAILURE,
        model="text-embedding-3-small",
        error_code="provider_timeout",
        profile_id=_active_profile_id(),
    )
    monkeypatch.setattr("app.execution.ingest.generate_embeddings_batch", lambda _texts: [failed])

    assert _embed_and_update_chunks(bundle_id) == 0

    chunk = _read_chunk(bundle_id)
    assert list(chunk.embedding) == pytest.approx(previous_vector)
    assert chunk.embedding_profile == previous_profile
    assert chunk.embedding_status == "transient_failure"
    assert chunk.embedding_error_code == "provider_timeout"


def test_missing_provider_does_not_mutate_existing_embedding(monkeypatch) -> None:
    bundle_id = _create_chunk()
    previous_vector = [0.3] * 1536
    previous_profile = _active_profile_id()
    _update_chunk_embedding(
        bundle_id,
        vector=previous_vector,
        profile_id=previous_profile,
        status="success",
    )
    for variable in (
        "EMBEDDING_API_KEY",
        "OPENROUTER_API_KEY",
        "DOCPILOT_PROVIDER_DOMESTIC_API_KEY",
        "ALIYUN_API_KEY",
        "DASHSCOPE_API_KEY",
        "DOCPILOT_PROVIDER_OPENAI_API_KEY",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(variable, raising=False)
    calls: list[list[str]] = []

    def _unexpected_provider_call(texts: list[str]):
        calls.append(texts)
        return []

    monkeypatch.setattr("app.execution.ingest.generate_embeddings_batch", _unexpected_provider_call)

    assert _embed_and_update_chunks(bundle_id) == 0
    assert calls == []

    chunk = _read_chunk(bundle_id)
    assert list(chunk.embedding) == pytest.approx(previous_vector)
    assert chunk.embedding_profile == previous_profile
    assert chunk.embedding_status == "success"


def test_embedding_batch_records_one_provider_usage_measurement(monkeypatch) -> None:
    bundle_id = _create_chunk()
    db = SessionLocal()
    try:
        source = (
            db.query(SourceDocument)
            .join(Bundle)
            .filter(Bundle.id == bundle_id)
            .one()
        )
        project = db.get(Project, source.bundle.project_id)
        assert project is not None
        db.add(
            KnowledgeChunk(
                id=f"chunk-second-{uuid.uuid4().hex[:8]}",
                project_id=project.id,
                source_document_id=source.id,
                chunk_index=1,
                content="系统必须支持本地化部署与审计追踪。",
            )
        )
        db.commit()
        org_id = project.org_id
    finally:
        db.close()

    profile = RetrievalProfile(
        provider="openrouter",
        model="qwen/qwen3-embedding-8b",
        dimensions=1536,
        normalizer_version="bidpilot-lexical-v1",
    )
    monkeypatch.setenv("DOCPILOT_ENV", "production")
    monkeypatch.setenv("DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING", "1000")
    monkeypatch.setattr("app.execution.ingest.get_embedding_profile", lambda: profile)
    monkeypatch.setattr(
        "app.execution.ingest.generate_embeddings_batch",
        lambda texts: [
            EmbeddingResult(
                status=EmbeddingOutcomeStatus.SUCCESS,
                model=profile.model,
                profile_id=profile.identifier,
                vector=[0.1] * 1536,
                token_count=9,
                usage_reported=True,
            )
            for _ in texts
        ],
    )

    assert _embed_and_update_chunks(bundle_id) == 2

    db = SessionLocal()
    try:
        records = list(
            db.query(ModelUsageRecord)
            .filter(
                ModelUsageRecord.org_id == org_id,
                ModelUsageRecord.workload == "embedding_bundle_index",
            )
            .all()
        )
        assert len(records) == 1
        assert records[0].input_tokens == 9
    finally:
        db.close()


def test_embedding_indexing_skips_provider_when_token_capacity_is_exhausted(monkeypatch) -> None:
    bundle_id = _create_chunk()
    profile = RetrievalProfile(
        provider="openrouter",
        model="qwen/qwen3-embedding-8b",
        dimensions=1536,
        normalizer_version="bidpilot-lexical-v1",
    )
    calls: list[list[str]] = []
    monkeypatch.setenv("DOCPILOT_ENV", "production")
    monkeypatch.setenv("DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING", "0")
    monkeypatch.setattr("app.execution.ingest.get_embedding_profile", lambda: profile)
    monkeypatch.setattr(
        "app.execution.ingest.generate_embeddings_batch",
        lambda texts: calls.append(texts),
    )

    assert _embed_and_update_chunks(bundle_id) == 0
    assert calls == []

    chunk = _read_chunk(bundle_id)
    assert chunk.embedding is None
    assert chunk.embedding_status == "budget_exhausted"
    assert chunk.embedding_error_code == "organization_token_budget_exhausted"
