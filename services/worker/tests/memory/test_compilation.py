from __future__ import annotations

from uuid import uuid4

from app.adapters.embedding import EmbeddingResult
from app.db import SessionLocal
from app.execution.memory import index_memory_records, run_compile_bid_wiki
from app.models import (
    Bundle,
    KnowledgeChunk,
    MemoryCompilationRun,
    MemoryEvidenceLink,
    MemoryRecord,
    Organization,
    Project,
    RequirementItem,
    SourceDocument,
)
from contracts import EmbeddingOutcomeStatus, RetrievalProfile, normalize_retrieval_text


PROFILE = RetrievalProfile(
    provider="test",
    model="embedding-test",
    dimensions=1536,
    normalizer_version="bidpilot-lexical-v1",
)


def _suffix() -> str:
    return uuid4().hex[:10]


def _seed_compilation() -> tuple[str, str, str, str]:
    suffix = _suffix()
    db = SessionLocal()
    try:
        org = Organization(id=f"org-wiki-{suffix}", slug=f"wiki-{suffix}", name="Wiki Test")
        project = Project(
            id=f"project-wiki-{suffix}",
            org_id=org.id,
            slug=f"wiki-{suffix}",
            name="Wiki Test",
            scenario_package="bidpilot",
        )
        bundle = Bundle(project_id=project.id, label="招标资料", source_type="upload", ingest_status="ingested")
        db.add_all([org, project, bundle])
        db.flush()
        source = SourceDocument(
            bundle_id=bundle.id,
            storage_key=f"uploads/{suffix}.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            checksum=suffix,
            original_filename="招标技术规范.docx",
            parse_status="parsed",
        )
        db.add(source)
        db.flush()
        db.add_all(
            [
                KnowledgeChunk(
                    project_id=project.id,
                    source_document_id=source.id,
                    chunk_index=0,
                    content="系统必须支持私有化部署，并提供不少于三年的运维服务。",
                    metadata_json={"source_document_id": source.id, "page": 3, "heading_path": ["技术要求"]},
                    retrieval_text=normalize_retrieval_text("系统必须支持私有化部署，并提供不少于三年的运维服务。"),
                ),
                KnowledgeChunk(
                    project_id=project.id,
                    source_document_id=source.id,
                    chunk_index=1,
                    content="投标人应当提供项目经理、交付计划和验收承诺。",
                    metadata_json={"source_document_id": source.id, "page": 4, "heading_path": ["交付要求"]},
                    retrieval_text=normalize_retrieval_text("投标人应当提供项目经理、交付计划和验收承诺。"),
                ),
            ]
        )
        run = MemoryCompilationRun(
            org_id=org.id,
            project_id=project.id,
            bundle_id=bundle.id,
            status="queued",
            input_source_ids_json=[source.id],
            input_memory_ids_json=[],
            policy_version="memory-compiler-v1",
        )
        db.add(run)
        db.commit()
        return run.id, project.id, source.id, bundle.id
    finally:
        db.close()


def test_compile_bid_wiki_creates_only_reviewable_source_backed_proposals() -> None:
    run_id, project_id, source_id, _bundle_id = _seed_compilation()

    result = run_compile_bid_wiki(run_id)

    assert result["status"] == "succeeded"
    db = SessionLocal()
    try:
        run = db.get(MemoryCompilationRun, run_id)
        assert run is not None
        assert run.status == "succeeded"
        assert run.result_json == {"proposals_created": 1, "proposals_skipped": 0, "source_documents_seen": 1}

        proposals = list(
            db.query(MemoryRecord)
            .filter(MemoryRecord.project_id == project_id, MemoryRecord.origin == "system")
            .all()
        )
        assert len(proposals) == 1
        proposal = proposals[0]
        assert proposal.status == "proposed"
        assert proposal.kind == "summary"
        assert proposal.embedding is None
        assert proposal.embedding_status == "pending"
        assert "私有化部署" in proposal.body_markdown
        links = list(
            db.query(MemoryEvidenceLink)
            .filter(MemoryEvidenceLink.memory_record_id == proposal.id)
            .all()
        )
        assert [link.source_type for link in links] == ["knowledge_chunk", "knowledge_chunk"]
        assert all(link.source_id for link in links)
        assert all(link.locator_json for link in links)
        assert source_id in {chunk.source_document_id for chunk in db.query(KnowledgeChunk).all()}
        assert db.query(RequirementItem).filter(RequirementItem.project_id == project_id).count() == 0
    finally:
        db.close()


def test_compile_bid_wiki_is_idempotent_for_same_source_snapshot() -> None:
    run_id, project_id, source_id, bundle_id = _seed_compilation()
    assert run_compile_bid_wiki(run_id)["status"] == "succeeded"

    db = SessionLocal()
    try:
        repeat = MemoryCompilationRun(
            org_id=db.get(Project, project_id).org_id,
            project_id=project_id,
            bundle_id=bundle_id,
            status="queued",
            input_source_ids_json=[source_id],
            input_memory_ids_json=[],
            policy_version="memory-compiler-v1",
        )
        db.add(repeat)
        db.commit()
        repeat_id = repeat.id
    finally:
        db.close()

    result = run_compile_bid_wiki(repeat_id)

    assert result == {"compilation_run_id": repeat_id, "status": "succeeded", "proposals_created": "0", "proposals_skipped": "1"}
    db = SessionLocal()
    try:
        assert db.query(MemoryRecord).filter(MemoryRecord.project_id == project_id).count() == 1
    finally:
        db.close()


def test_memory_indexing_preserves_previous_vector_on_provider_failure(monkeypatch) -> None:
    suffix = _suffix()
    db = SessionLocal()
    try:
        org = Organization(id=f"org-index-{suffix}", slug=f"index-{suffix}", name="Index Test")
        project = Project(
            id=f"project-index-{suffix}",
            org_id=org.id,
            slug=f"index-{suffix}",
            name="Index Test",
            scenario_package="bidpilot",
        )
        db.add_all([org, project])
        db.flush()
        record = MemoryRecord(
            org_id=org.id,
            project_id=project.id,
            scope="project_shared",
            kind="summary",
            status="active",
            title="已有摘要",
            body_markdown="已有向量在临时失败后仍必须保留。",
            retrieval_text=normalize_retrieval_text("已有摘要\n已有向量在临时失败后仍必须保留。"),
            embedding=[0.25, 0.75] + [0.0] * 1534,
            embedding_profile="old-profile",
            embedding_status="success",
            origin="system",
            created_by_actor_type="system",
            created_by_actor_id="memory-compiler",
        )
        db.add(record)
        db.commit()
        record_id = record.id
    finally:
        db.close()

    monkeypatch.setattr("app.execution.memory.get_embedding_profile", lambda: PROFILE)
    monkeypatch.setattr(
        "app.execution.memory.generate_embeddings_batch",
        lambda _texts: [
            EmbeddingResult(
                status=EmbeddingOutcomeStatus.TRANSIENT_FAILURE,
                model="embedding-test",
                profile_id=PROFILE.identifier,
                error_code="provider_unavailable",
            )
        ],
    )

    result = index_memory_records([record_id])

    assert result == {"status": "completed", "indexed": "0", "failed": "1"}
    db = SessionLocal()
    try:
        record = db.get(MemoryRecord, record_id)
        assert record is not None
        assert list(record.embedding)[:2] == [0.25, 0.75]
        assert record.embedding_profile == "old-profile"
        assert record.embedding_status == "transient_failure"
        assert record.embedding_error_code == "provider_unavailable"
    finally:
        db.close()


def test_memory_indexing_never_batches_records_from_different_organizations(monkeypatch) -> None:
    suffix = _suffix()
    db = SessionLocal()
    try:
        org_one = Organization(id=f"org-isolation-one-{suffix}", slug=f"isolation-one-{suffix}", name="Isolation One")
        org_two = Organization(id=f"org-isolation-two-{suffix}", slug=f"isolation-two-{suffix}", name="Isolation Two")
        project_one = Project(
            id=f"project-isolation-one-{suffix}",
            org_id=org_one.id,
            slug=f"isolation-one-{suffix}",
            name="Isolation One Project",
            scenario_package="bidpilot",
        )
        project_two = Project(
            id=f"project-isolation-two-{suffix}",
            org_id=org_two.id,
            slug=f"isolation-two-{suffix}",
            name="Isolation Two Project",
            scenario_package="bidpilot",
        )
        record_one = MemoryRecord(
            org_id=org_one.id,
            project_id=project_one.id,
            scope="project_shared",
            kind="summary",
            status="active",
            title="组织一资料",
            body_markdown="组织一的私有投标内容。",
            retrieval_text=normalize_retrieval_text("组织一资料\n组织一的私有投标内容。"),
            embedding_status="pending",
            origin="system",
            created_by_actor_type="system",
            created_by_actor_id="test",
        )
        record_two = MemoryRecord(
            org_id=org_two.id,
            project_id=project_two.id,
            scope="project_shared",
            kind="summary",
            status="active",
            title="组织二资料",
            body_markdown="组织二的私有投标内容。",
            retrieval_text=normalize_retrieval_text("组织二资料\n组织二的私有投标内容。"),
            embedding_status="pending",
            origin="system",
            created_by_actor_type="system",
            created_by_actor_id="test",
        )
        db.add_all([org_one, org_two])
        db.flush()
        db.add_all([project_one, project_two])
        db.flush()
        db.add_all([record_one, record_two])
        db.commit()
        record_ids = [record_one.id, record_two.id]
    finally:
        db.close()

    calls: list[list[str]] = []
    monkeypatch.setattr("app.execution.memory.get_embedding_profile", lambda: PROFILE)

    def _embed(texts: list[str]) -> list[EmbeddingResult]:
        calls.append(texts)
        return [
            EmbeddingResult(
                status=EmbeddingOutcomeStatus.SUCCESS,
                model=PROFILE.model,
                profile_id=PROFILE.identifier,
                vector=[0.1] * 1536,
                token_count=3,
                usage_reported=True,
            )
            for _ in texts
        ]

    monkeypatch.setattr("app.execution.memory.generate_embeddings_batch", _embed)

    result = index_memory_records(record_ids)

    assert result == {"status": "completed", "indexed": "2", "failed": "0"}
    assert len(calls) == 2
    assert {tuple(batch) for batch in calls} == {
        ("组织一资料\n组织一的私有投标内容。",),
        ("组织二资料\n组织二的私有投标内容。",),
    }
