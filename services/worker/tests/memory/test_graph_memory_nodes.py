from __future__ import annotations

from uuid import uuid4

from app.adapters.embedding import EmbeddingResult
from app.db import SessionLocal
from app.graph.nodes.memory_context import load_memory_context_node
from app.graph.nodes.memory_proposals import propose_memory_updates_node
from app.models import Bundle, KnowledgeChunk, MemoryEvidenceLink, MemoryRecord, Organization, Project, ProjectMember, RuntimeRun, SourceDocument, User
from contracts import EmbeddingOutcomeStatus, normalize_retrieval_text


def test_graph_loads_only_the_runtime_initiators_authorized_memory(monkeypatch) -> None:
    suffix = uuid4().hex[:10]
    db = SessionLocal()
    try:
        org = Organization(id=f"org-graph-memory-{suffix}", slug=f"graph-memory-{suffix}", name="Graph Memory")
        project = Project(
            id=f"project-graph-{suffix}",
            org_id=org.id,
            slug=f"graph-{suffix}",
            name="Graph Memory",
            scenario_package="bidpilot",
        )
        owner = User(
            id=f"user-owner-{suffix}",
            org_id=org.id,
            email=f"owner-{suffix}@example.test",
            display_name="Owner",
            role="member",
            password_hash="test-only",
        )
        other_user = User(
            id=f"user-other-{suffix}",
            org_id=org.id,
            email=f"other-{suffix}@example.test",
            display_name="Other",
            role="member",
            password_hash="test-only",
        )
        db.add_all([org, project, owner, other_user])
        db.flush()
        db.add(ProjectMember(project_id=project.id, user_id=owner.id, role="owner"))
        runtime_run = RuntimeRun(
            kind="workflow_bridge",
            status="running",
            org_id=org.id,
            user_id=owner.id,
            project_id=project.id,
            engine="langgraph_workflow",
            trace_id=f"memory-graph-{suffix}",
            policy_snapshot_json={"approval_mode": "risky_only"},
        )
        owner_memory = MemoryRecord(
            org_id=org.id,
            owner_user_id=owner.id,
            scope="user_private",
            kind="preference",
            status="active",
            title="写作偏好",
            body_markdown="技术方案先给出结论，再说明风险。",
            retrieval_text=normalize_retrieval_text("写作偏好\n技术方案先给出结论，再说明风险。"),
            embedding_status="pending",
            origin="user",
            created_by_actor_type="user",
            created_by_actor_id=owner.id,
        )
        other_memory = MemoryRecord(
            org_id=org.id,
            owner_user_id=other_user.id,
            scope="user_private",
            kind="preference",
            status="active",
            title="他人偏好",
            body_markdown="不得被当前工作流读取。",
            retrieval_text=normalize_retrieval_text("他人偏好\n不得被当前工作流读取。"),
            embedding_status="pending",
            origin="user",
            created_by_actor_type="user",
            created_by_actor_id=other_user.id,
        )
        db.add_all([runtime_run, owner_memory, other_memory])
        db.flush()
        db.add_all(
            [
                MemoryEvidenceLink(
                    memory_record_id=owner_memory.id,
                    source_type="human_decision",
                    source_id=owner.id,
                    label="用户明确写入",
                ),
                MemoryEvidenceLink(
                    memory_record_id=other_memory.id,
                    source_type="human_decision",
                    source_id=other_user.id,
                    label="用户明确写入",
                ),
            ]
        )
        db.commit()
        runtime_run_id = runtime_run.id
        project_id = project.id
    finally:
        db.close()

    monkeypatch.setattr(
        "app.graph.nodes.memory_context.generate_metered_embedding",
        lambda *_args, **_kwargs: EmbeddingResult(
            status=EmbeddingOutcomeStatus.NOT_CONFIGURED,
            model="not_configured",
            error_code="embedding_not_configured",
        ),
    )

    result = load_memory_context_node(
        {
            "project_id": project_id,
            "section_key": "technical-approach",
            "runtime_run_id": runtime_run_id,
            "requirements": [],
        }
    )

    assert result["memory_context_loaded"] is True
    assert result["memory_context_version"]
    assert result["memory_context_items"] == [
        {
            "title": "写作偏好",
            "body_markdown": "技术方案先给出结论，再说明风险。",
            "scope": "user_private",
            "kind": "preference",
            "citations": ["用户明确写入"],
        }
    ]
    assert "dense_unavailable" in result["memory_context_degraded_reasons"]

    with SessionLocal() as db:
        membership = db.query(ProjectMember).filter_by(project_id=project_id, user_id=owner.id).one()
        db.delete(membership)
        db.commit()

    revoked = load_memory_context_node(
        {
            "project_id": project_id,
            "section_key": "technical-approach",
            "runtime_run_id": runtime_run_id,
            "requirements": [],
        }
    )

    assert revoked["memory_context_items"] == []
    assert revoked["memory_context_degraded_reasons"] == ["runtime_principal_memory_access_revoked"]


def test_graph_memory_context_degrades_when_runtime_principal_is_missing() -> None:
    result = load_memory_context_node(
        {
            "project_id": "project-missing",
            "section_key": "technical-approach",
            "runtime_run_id": None,
            "requirements": [],
        }
    )

    assert result["memory_context_loaded"] is True
    assert result["memory_context_items"] == []
    assert result["memory_context_degraded_reasons"] == ["missing_runtime_principal"]


def test_graph_only_proposes_memory_after_approved_evidence_backed_persistence() -> None:
    suffix = uuid4().hex[:10]
    db = SessionLocal()
    try:
        org = Organization(id=f"org-proposal-{suffix}", slug=f"proposal-{suffix}", name="Proposal Test")
        project = Project(
            id=f"project-proposal-{suffix}",
            org_id=org.id,
            slug=f"proposal-{suffix}",
            name="Proposal Test",
            scenario_package="bidpilot",
        )
        db.add_all([org, project])
        db.flush()
        bundle = Bundle(project_id=project.id, label="材料", source_type="upload")
        db.add(bundle)
        db.flush()
        source = SourceDocument(
            bundle_id=bundle.id,
            storage_key=f"uploads/{suffix}.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            checksum=suffix,
            original_filename="技术规范.docx",
            parse_status="parsed",
        )
        db.add(source)
        db.flush()
        chunk = KnowledgeChunk(
            project_id=project.id,
            source_document_id=source.id,
            chunk_index=0,
            content="系统必须支持私有化部署。",
            retrieval_text=normalize_retrieval_text("系统必须支持私有化部署。"),
        )
        db.add(chunk)
        db.commit()
        project_id = project.id
        chunk_id = chunk.id
        source_id = source.id
    finally:
        db.close()

    state = {
        "project_id": project_id,
        "section_key": "technical-approach",
        "section_version_id": "version-graph-memory",
        "persisted": True,
        "review_passed": True,
        "human_decision": "approved",
        "draft_markdown": "## 技术方案\n\n系统支持私有化部署。",
        "evidence_chunks": [
            {
                "chunk_id": chunk_id,
                "source_document_id": source_id,
                "content": "系统必须支持私有化部署。",
                "locator_json": {"page": 3, "chunk_index": 0},
            }
        ],
    }

    first = propose_memory_updates_node(state)
    second = propose_memory_updates_node(state)

    assert len(first["memory_proposal_ids"]) == 1
    assert second["memory_proposal_ids"] == []
    db = SessionLocal()
    try:
        proposal = db.get(MemoryRecord, first["memory_proposal_ids"][0])
        assert proposal is not None
        assert proposal.status == "proposed"
        assert proposal.kind == "summary"
        assert proposal.origin == "system"
        links = db.query(MemoryEvidenceLink).filter_by(memory_record_id=proposal.id).all()
        assert [(link.source_type, link.source_id) for link in links] == [("knowledge_chunk", chunk_id)]
    finally:
        db.close()
