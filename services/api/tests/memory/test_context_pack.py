from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.db import SessionLocal
from app.models import Bundle, KnowledgeChunk, MemoryEvidenceLink, MemoryRecord, Organization, Project, SourceDocument, User
from contracts import normalize_retrieval_text
from contracts.memory_service import build_memory_context_pack


PROFILE_ID = "openrouter:qwen/qwen3-embedding-8b:1536:bidpilot-lexical-v1"


def _vector(first: float, second: float) -> list[float]:
    return [first, second] + [0.0] * 1534


def _add_record(
    db,
    *,
    record_id: str,
    org_id: str,
    project_id: str | None,
    owner_user_id: str | None,
    scope: str,
    title: str,
    body: str,
    status: str = "active",
    expires_at=None,
    embedding=None,
    embedding_profile=None,
    deleted_at=None,
    citation_source_id: str | None = None,
) -> None:
    record = MemoryRecord(
        id=record_id,
        org_id=org_id,
        project_id=project_id,
        owner_user_id=owner_user_id,
        scope=scope,
        kind="fact" if scope != "user_private" else "preference",
        status=status,
        title=title,
        body_markdown=body,
        retrieval_text=normalize_retrieval_text(f"{title}\n{body}"),
        embedding=embedding,
        embedding_profile=embedding_profile,
        embedding_status="success" if embedding else "pending",
        origin="user",
        created_by_actor_type="user",
        created_by_actor_id=owner_user_id or "user-memory-context",
        expires_at=expires_at,
        deleted_at=deleted_at,
    )
    db.add(record)
    db.flush()
    db.add(
        MemoryEvidenceLink(
            memory_record_id=record.id,
            source_type="human_decision" if scope == "user_private" else "knowledge_chunk",
            source_id=owner_user_id or citation_source_id or "chunk-deployment",
            label="用户明确设置" if scope == "user_private" else "技术规范，第 3 节",
        )
    )


def _seed_memory() -> tuple[str, str, str, str, dict[str, str]]:
    db = SessionLocal()
    try:
        suffix = uuid4().hex[:12]
        now = datetime.now(UTC).replace(tzinfo=None)
        org = Organization(id=f"org-memory-{suffix}", slug=f"memory-{suffix}", name="Memory Context")
        project = Project(
            id=f"project-memory-{suffix}",
            org_id=org.id,
            slug=f"memory-{suffix}",
            name="Memory Context",
            scenario_package="bidpilot",
        )
        foreign_project = Project(
            id=f"project-foreign-{suffix}",
            org_id=org.id,
            slug=f"foreign-{suffix}",
            name="Memory Foreign",
            scenario_package="bidpilot",
        )
        user = User(
            id=f"user-memory-{suffix}",
            org_id=org.id,
            email=f"memory-context-{suffix}@example.test",
            display_name="Memory Context",
            role="member",
            password_hash="test-only",
        )
        other_user = User(
            id=f"user-other-{suffix}",
            org_id=org.id,
            email=f"memory-other-{suffix}@example.test",
            display_name="Memory Other",
            role="member",
            password_hash="test-only",
        )
        db.add_all([org, project, foreign_project, user, other_user])
        db.commit()
        bundle = Bundle(
            id=f"bundle-memory-{suffix}",
            project_id=project.id,
            label="技术规范",
            source_type="upload",
            ingest_status="ingested",
        )
        source = SourceDocument(
            id=f"source-memory-{suffix}",
            bundle_id=bundle.id,
            storage_key=f"uploads/{suffix}/technical-spec.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            checksum="a" * 64,
            original_filename="技术规范.docx",
            parse_status="parsed",
            index_status="indexed",
        )
        db.add_all([bundle, source])
        # KnowledgeChunk intentionally has no ORM relationship to SourceDocument,
        # so flush the document first instead of relying on unit-of-work ordering.
        db.flush()
        chunk = KnowledgeChunk(
            id=f"chunk-deployment-{suffix}",
            project_id=project.id,
            source_document_id=source.id,
            chunk_index=0,
            content="投标方案必须支持私有化部署和离线交付。",
            retrieval_text="投标方案必须支持私有化部署和离线交付。",
        )
        db.add(chunk)
        db.commit()
        _add_record(
            db,
            record_id=f"memory-project-{suffix}",
            org_id=org.id,
            project_id=project.id,
            owner_user_id=None,
            scope="project_shared",
            title="部署约束",
            body="投标方案必须支持私有化部署和离线交付。",
            embedding=_vector(1.0, 0.0),
            embedding_profile=PROFILE_ID,
            citation_source_id=chunk.id,
        )
        _add_record(
            db,
            record_id=f"memory-private-{suffix}",
            org_id=org.id,
            project_id=None,
            owner_user_id=user.id,
            scope="user_private",
            title="写作偏好",
            body="先给出结论，再补充证据和风险。",
            embedding=_vector(0.0, 1.0),
            embedding_profile=PROFILE_ID,
        )
        _add_record(
            db,
            record_id=f"memory-private-other-{suffix}",
            org_id=org.id,
            project_id=None,
            owner_user_id=other_user.id,
            scope="user_private",
            title="他人偏好",
            body="不得泄露给当前用户。",
        )
        _add_record(
            db,
            record_id=f"memory-foreign-{suffix}",
            org_id=org.id,
            project_id=foreign_project.id,
            owner_user_id=None,
            scope="project_shared",
            title="其他项目",
            body="其他项目的私有化部署约束不能混入。",
        )
        _add_record(
            db,
            record_id=f"memory-expired-{suffix}",
            org_id=org.id,
            project_id=project.id,
            owner_user_id=None,
            scope="project_shared",
            title="已过期",
            body="过期内容不能进入上下文。",
            expires_at=now - timedelta(seconds=1),
        )
        _add_record(
            db,
            record_id=f"memory-superseded-{suffix}",
            org_id=org.id,
            project_id=project.id,
            owner_user_id=None,
            scope="project_shared",
            title="已替代",
            body="已替代内容不能进入上下文。",
            status="superseded",
        )
        _add_record(
            db,
            record_id=f"memory-deleted-{suffix}",
            org_id=org.id,
            project_id=project.id,
            owner_user_id=None,
            scope="project_shared",
            title="已删除",
            body="已删除内容不能进入上下文。",
            deleted_at=now,
        )
        db.commit()
        return org.id, user.id, project.id, foreign_project.id, {
            "project": f"memory-project-{suffix}",
            "private": f"memory-private-{suffix}",
            "project_source_document": source.id,
        }
    finally:
        db.close()


def test_context_pack_is_scope_safe_and_degrades_to_lexical_recall() -> None:
    org_id, user_id, project_id, _foreign_project_id, record_ids = _seed_memory()
    db = SessionLocal()
    try:
        pack = build_memory_context_pack(
            db,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            raw_query="私有化部署和写作偏好",
            profile_id=None,
            query_embedding=None,
            top_k=8,
            max_characters=2000,
        )
    finally:
        db.close()

    assert [item.record_id for item in pack.items] == [record_ids["project"], record_ids["private"]]
    assert "dense_unavailable" in pack.degraded_reasons
    assert all(item.citations for item in pack.items)
    assert pack.memory_version


def test_context_pack_only_uses_matching_profile_for_dense_memory() -> None:
    org_id, user_id, project_id, _foreign_project_id, record_ids = _seed_memory()
    db = SessionLocal()
    try:
        pack = build_memory_context_pack(
            db,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            raw_query="部署",
            profile_id=PROFILE_ID,
            query_embedding=_vector(1.0, 0.0),
            top_k=1,
            max_characters=2000,
        )
    finally:
        db.close()

    assert [item.record_id for item in pack.items] == [record_ids["project"]]


def test_context_pack_can_disable_private_preferences_without_hiding_project_knowledge() -> None:
    org_id, user_id, project_id, _foreign_project_id, record_ids = _seed_memory()
    db = SessionLocal()
    try:
        pack = build_memory_context_pack(
            db,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            raw_query="私有化部署和写作偏好",
            profile_id=None,
            query_embedding=None,
            top_k=8,
            max_characters=2000,
            include_user_private=False,
        )
    finally:
        db.close()

    record_ids_in_pack = {item.record_id for item in pack.items}
    assert record_ids["project"] in record_ids_in_pack
    assert record_ids["private"] not in record_ids_in_pack


def test_context_pack_tombstones_change_the_memory_version() -> None:
    org_id, user_id, project_id, _foreign_project_id, record_ids = _seed_memory()
    db = SessionLocal()
    try:
        before = build_memory_context_pack(
            db,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            raw_query="私有化部署",
            profile_id=None,
            query_embedding=None,
            top_k=8,
            max_characters=2000,
        )
        record = db.get(MemoryRecord, record_ids["project"])
        assert record is not None
        record.status = "deleted"
        record.deleted_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()
        after = build_memory_context_pack(
            db,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            raw_query="私有化部署",
            profile_id=None,
            query_embedding=None,
            top_k=8,
            max_characters=2000,
        )
    finally:
        db.close()

    assert record_ids["project"] in {item.record_id for item in before.items}
    assert record_ids["project"] not in {item.record_id for item in after.items}
    assert before.memory_version != after.memory_version


def test_context_pack_excludes_memory_when_its_document_source_is_invalidated() -> None:
    org_id, user_id, project_id, _foreign_project_id, record_ids = _seed_memory()
    db = SessionLocal()
    try:
        before = build_memory_context_pack(
            db,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            raw_query="私有化部署",
            profile_id=None,
            query_embedding=None,
            top_k=8,
            max_characters=2000,
        )
        source = db.get(SourceDocument, record_ids["project_source_document"])
        assert source is not None
        source.parse_status = "failed"
        db.commit()
        after = build_memory_context_pack(
            db,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            raw_query="私有化部署",
            profile_id=None,
            query_embedding=None,
            top_k=8,
            max_characters=2000,
        )
    finally:
        db.close()

    assert record_ids["project"] in {item.record_id for item in before.items}
    assert record_ids["project"] not in {item.record_id for item in after.items}
    assert "invalid_memory_evidence" in after.degraded_reasons
    assert before.memory_version != after.memory_version
