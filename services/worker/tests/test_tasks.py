import uuid

from app.db import SessionLocal
from app.models import AssistantAttachment, Bundle, ExecutionRun, KnowledgeChunk, Organization, Project, RuntimeRun, SourceDocument
from app.tasks import cleanup_assistant_attachments, draft_section, ingest_bundle, ping, reindex_bundle
from contracts.models import User


def _unique_suffix() -> str:
    return uuid.uuid4().hex[:8]


def _ensure_test_org(db) -> str:
    org = db.get(Organization, "00000000-0000-0000-0000-000000000001")
    if org is None:
        org = Organization(
            id="00000000-0000-0000-0000-000000000001",
            slug="default",
            name="Default Organization",
        )
        db.add(org)
        db.commit()
    return org.id


def test_ping_task() -> None:
    assert ping() == "pong"


def test_ingest_bundle_task() -> None:
    db = SessionLocal()
    try:
        s = _unique_suffix()
        project = Project(
            name=f"Ingest Test {s}",
            slug=f"ingest-test-{s}",
            scenario_package="bidpilot",
            org_id=_ensure_test_org(db),
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        bundle = Bundle(project_id=project.id, label="Test Bundle", source_type="upload")
        db.add(bundle)
        db.commit()
        db.refresh(bundle)
        bundle_id = bundle.id
    finally:
        db.close()

    result = ingest_bundle(bundle_id)
    assert result["bundle_id"] == bundle_id
    assert result["status"] == "ingested"

    # Verify DB state
    db = SessionLocal()
    try:
        b = db.get(Bundle, bundle_id)
        assert b is not None
        assert b.ingest_status == "ingested"
    finally:
        db.close()


def test_draft_section_task() -> None:
    db = SessionLocal()
    try:
        s = _unique_suffix()
        project = Project(
            name=f"Draft Test {s}",
            slug=f"draft-test-{s}",
            scenario_package="bidpilot",
            org_id=_ensure_test_org(db),
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        run = ExecutionRun(project_id=project.id, run_type="draft_section")
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id
        project_id = project.id
    finally:
        db.close()

    result = draft_section(run_id, project_id, "technical-approach")
    assert result["run_id"] == run_id
    assert result["status"] == "succeeded"

    # Verify DB state
    db = SessionLocal()
    try:
        r = db.get(ExecutionRun, run_id)
        assert r is not None
        assert r.status == "succeeded"
        assert r.finished_at is not None
    finally:
        db.close()


def test_reindex_bundle_task_never_reparses_or_reextracts(monkeypatch) -> None:
    db = SessionLocal()
    try:
        suffix = _unique_suffix()
        project = Project(
            name=f"Reindex Test {suffix}",
            slug=f"reindex-test-{suffix}",
            scenario_package="bidpilot",
            org_id=_ensure_test_org(db),
        )
        db.add(project)
        db.flush()
        bundle = Bundle(project_id=project.id, label="Reindex Bundle", source_type="upload")
        db.add(bundle)
        db.flush()
        source = SourceDocument(
            bundle_id=bundle.id,
            storage_key="uploads/reindex.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            checksum=suffix,
            original_filename="reindex.docx",
            parse_status="parsed",
        )
        db.add(source)
        db.flush()
        db.add(
            KnowledgeChunk(
                project_id=project.id,
                source_document_id=source.id,
                chunk_index=0,
                content="已经解析的材料只允许刷新向量。",
            )
        )
        db.commit()
        bundle_id = bundle.id
    finally:
        db.close()

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("reindex must not parse documents or extract requirements")

    def _complete_embedding(target_bundle_id: str) -> int:
        db = SessionLocal()
        try:
            chunks = list(
                db.query(KnowledgeChunk)
                .join(SourceDocument, SourceDocument.id == KnowledgeChunk.source_document_id)
                .filter(SourceDocument.bundle_id == target_bundle_id)
                .all()
            )
            for chunk in chunks:
                chunk.embedding = [0.1] * 1536
                chunk.embedding_status = "success"
                chunk.embedding_error_code = None
            db.commit()
            return len(chunks)
        finally:
            db.close()

    monkeypatch.setattr("app.execution.ingest.parse_bundle_documents", _forbidden)
    monkeypatch.setattr("app.execution.ingest._extract_and_store_requirements", _forbidden)
    monkeypatch.setattr("app.execution.ingest._embed_and_update_chunks", _complete_embedding)

    result = reindex_bundle(bundle_id)

    assert result == {"bundle_id": bundle_id, "status": "reindexed", "chunks_embedded": "1"}
    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        assert bundle is not None
        assert bundle.ingest_status == "ingested"
    finally:
        db.close()


def test_cleanup_assistant_attachments_removes_expired_staging_objects(monkeypatch) -> None:
    from datetime import UTC, datetime, timedelta

    db = SessionLocal()
    try:
        suffix = _unique_suffix()
        org_id = _ensure_test_org(db)
        user = User(
            org_id=org_id,
            email=f"attachment-cleanup-{suffix}@example.test",
            display_name="Attachment Cleanup",
            role="admin",
            password_hash="test-only",
        )
        db.add(user)
        db.flush()
        attachment = AssistantAttachment(
            user_id=user.id,
            org_id=org_id,
            storage_key=f"docpilot-assistant-staging/assistant-attachments/{suffix}",
            original_filename="stale.txt",
            mime_type="text/plain",
            kind="file",
            size=12,
            checksum=suffix.ljust(64, "0"),
            extraction_status="extracted",
            extracted_text="stale private text",
            status="staged",
            expires_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1),
        )
        db.add(attachment)
        db.commit()
        attachment_id = attachment.id
    finally:
        db.close()

    deleted: list[str] = []
    monkeypatch.setattr("app.execution.assistant_attachments.delete_storage_key", lambda key: deleted.append(key))

    result = cleanup_assistant_attachments()

    assert result["status"] == "ok"
    assert int(result["deleted"]) >= 1
    assert f"docpilot-assistant-staging/assistant-attachments/{suffix}" in deleted
    db = SessionLocal()
    try:
        attachment = db.get(AssistantAttachment, attachment_id)
        assert attachment is not None
        assert attachment.status == "expired"
        assert attachment.storage_key == ""
        assert attachment.extracted_text == ""
    finally:
        db.close()


def test_draft_section_stops_before_legacy_work_when_runtime_cancellation_is_requested(monkeypatch) -> None:
    db = SessionLocal()
    try:
        suffix = _unique_suffix()
        org_id = _ensure_test_org(db)
        user = User(
            org_id=org_id,
            email=f"cancel-worker-{suffix}@example.test",
            display_name="Cancellation Worker",
            role="admin",
            password_hash="test-only",
        )
        db.add(user)
        db.flush()
        project = Project(
            name=f"Cancelled Draft {suffix}",
            slug=f"cancelled-draft-{suffix}",
            scenario_package="bidpilot",
            org_id=org_id,
        )
        db.add(project)
        db.flush()
        run = ExecutionRun(project_id=project.id, run_type="draft_section", status="cancel_requested")
        db.add(run)
        db.flush()
        runtime_run = RuntimeRun(
            kind="workflow_bridge",
            status="cancel_requested",
            org_id=org_id,
            user_id=user.id,
            project_id=project.id,
            execution_run_id=run.id,
            engine="langgraph_workflow",
            trace_id=f"cancel-trace-{suffix}",
            policy_snapshot_json={"approval_mode": "risky_only"},
        )
        db.add(runtime_run)
        db.commit()
        run_id = run.id
        project_id = project.id
        runtime_run_id = runtime_run.id
    finally:
        db.close()

    called = False

    def should_not_draft(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("cancelled work must not call the drafting executor")

    monkeypatch.setattr("app.graph.builder.invoke_graph", should_not_draft)

    result = draft_section(run_id, project_id, "technical-approach", runtime_run_id=runtime_run_id)

    assert result["status"] == "cancelled"
    assert called is False
    db = SessionLocal()
    try:
        run = db.get(ExecutionRun, run_id)
        runtime_run = db.get(RuntimeRun, runtime_run_id)
        assert run is not None and run.status == "cancelled"
        assert runtime_run is not None and runtime_run.status == "cancelled"
    finally:
        db.close()


def test_draft_section_cancels_after_graph_work_when_request_arrives_in_flight(monkeypatch) -> None:
    db = SessionLocal()
    try:
        suffix = _unique_suffix()
        org_id = _ensure_test_org(db)
        user = User(
            org_id=org_id,
            email=f"in-flight-cancel-{suffix}@example.test",
            display_name="In-flight Cancellation Worker",
            role="admin",
            password_hash="test-only",
        )
        db.add(user)
        db.flush()
        project = Project(
            name=f"In-flight Cancelled Draft {suffix}",
            slug=f"in-flight-cancelled-draft-{suffix}",
            scenario_package="bidpilot",
            org_id=org_id,
        )
        db.add(project)
        db.flush()
        run = ExecutionRun(project_id=project.id, run_type="draft_section", status="running")
        db.add(run)
        db.flush()
        runtime_run = RuntimeRun(
            kind="workflow_bridge",
            status="running",
            org_id=org_id,
            user_id=user.id,
            project_id=project.id,
            execution_run_id=run.id,
            engine="langgraph_workflow",
            trace_id=f"in-flight-cancel-trace-{suffix}",
            policy_snapshot_json={"approval_mode": "risky_only"},
        )
        db.add(runtime_run)
        db.commit()
        run_id = run.id
        project_id = project.id
        runtime_run_id = runtime_run.id
    finally:
        db.close()

    def graph_then_request_cancellation(*_args, **_kwargs):
        worker_db = SessionLocal()
        try:
            persisted = worker_db.get(RuntimeRun, runtime_run_id)
            assert persisted is not None
            persisted.status = "cancel_requested"
            worker_db.commit()
        finally:
            worker_db.close()
        return {
            "persisted": True,
            "section_key": "technical-approach",
            "section_version_id": "candidate-version",
        }

    monkeypatch.setattr("app.graph.builder.invoke_graph", graph_then_request_cancellation)

    result = draft_section(run_id, project_id, "technical-approach", runtime_run_id=runtime_run_id)

    assert result["status"] == "cancelled"
    db = SessionLocal()
    try:
        run = db.get(ExecutionRun, run_id)
        runtime_run = db.get(RuntimeRun, runtime_run_id)
        assert run is not None and run.status == "cancelled"
        assert runtime_run is not None and runtime_run.status == "cancelled"
    finally:
        db.close()
