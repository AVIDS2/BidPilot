
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.schemas import CurrentUser
from app.auth.service import _hash_password, require_auth
from app.db import Base, get_db
from app.memory.mem0_provider import Mem0ProfileMemory
from app.main import app
from app.models import (
    Bundle,
    ExecutionRun,
    KnowledgeChunk,
    MemoryCompilationRun,
    MemoryEntity,
    MemoryEvidenceLink,
    MemoryEvent,
    MemoryRelation,
    MemoryRecord,
    Organization,
    OrganizationMembership,
    Project,
    ProjectMember,
    RuntimeRun,
    SourceDocument,
    TaskOutboxEvent,
    UsageEvent,
    User,
)
from app.usage.schemas import ProviderSource
from app.usage.service import EMBEDDING_INDEX_STARTED, record_usage_event


def _current(user: User) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        plan="professional",
        email_verified=True,
        disabled=False,
        memory_enabled=user.memory_enabled,
        org_id=user.org_id,
        org_slug="acme",
    )


@pytest.fixture()
def memory_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as db:
        org = Organization(id="org-memory", slug="memory", name="Memory Org")
        other_org = Organization(id="org-other-memory", slug="other-memory", name="Other Org")
        project = Project(
            id="project-memory",
            org_id=org.id,
            slug="memory-bid",
            name="Memory Bid",
            scenario_package="bidpilot",
        )
        users = {
            "owner": User(
                id="user-memory-owner",
                org_id=org.id,
                email="owner@memory.test",
                display_name="Owner",
                password_hash=_hash_password("Test1234"),
                role="member",
                email_verified=True,
            ),
            "contributor": User(
                id="user-memory-contributor",
                org_id=org.id,
                email="contributor@memory.test",
                display_name="Contributor",
                password_hash=_hash_password("Test1234"),
                role="member",
                email_verified=True,
            ),
            "viewer": User(
                id="user-memory-viewer",
                org_id=org.id,
                email="viewer@memory.test",
                display_name="Viewer",
                password_hash=_hash_password("Test1234"),
                role="member",
                email_verified=True,
            ),
            "outsider": User(
                id="user-memory-outsider",
                org_id=other_org.id,
                email="outsider@other-memory.test",
                display_name="Outsider",
                password_hash=_hash_password("Test1234"),
                role="member",
                email_verified=True,
            ),
        }
        db.add_all([org, other_org, project, *users.values()])
        db.flush()
        db.add_all(
            [
                OrganizationMembership(
                    org_id=org.id,
                    user_id=users[role].id,
                    role="owner" if role == "owner" else "member",
                )
                for role in ("owner", "contributor", "viewer")
            ]
            + [
                OrganizationMembership(
                    org_id=other_org.id,
                    user_id=users["outsider"].id,
                    role="owner",
                )
            ]
        )
        db.add_all(
            [
                ProjectMember(project_id=project.id, user_id=users["owner"].id, role="owner"),
                ProjectMember(project_id=project.id, user_id=users["contributor"].id, role="contributor"),
                ProjectMember(project_id=project.id, user_id=users["viewer"].id, role="viewer"),
            ]
        )
        foreign_project = Project(
            id="project-memory-foreign",
            org_id=org.id,
            slug="foreign-memory-bid",
            name="Foreign Memory Bid",
            scenario_package="bidpilot",
        )
        bundle = Bundle(id="bundle-memory", project_id=project.id, label="Memory source", source_type="upload")
        foreign_bundle = Bundle(
            id="bundle-memory-foreign",
            project_id=foreign_project.id,
            label="Foreign memory source",
            source_type="upload",
        )
        db.add_all([foreign_project, bundle, foreign_bundle])
        db.flush()
        source = SourceDocument(
            id="source-memory",
            bundle_id=bundle.id,
            storage_key="uploads/memory-source.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            checksum="memory-source-checksum",
            original_filename="技术规范.docx",
            parse_status="parsed",
        )
        foreign_source = SourceDocument(
            id="source-memory-foreign",
            bundle_id=foreign_bundle.id,
            storage_key="uploads/foreign-memory-source.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            checksum="foreign-memory-source-checksum",
            original_filename="其他项目技术规范.docx",
            parse_status="parsed",
        )
        db.add_all([source, foreign_source])
        db.flush()
        db.add_all(
            [
                KnowledgeChunk(
                    id="chunk-deployment",
                    project_id=project.id,
                    source_document_id=source.id,
                    chunk_index=0,
                    content="系统必须支持私有化部署。",
                    metadata_json={},
                ),
                KnowledgeChunk(
                    id="chunk-foreign",
                    project_id=foreign_project.id,
                    source_document_id=foreign_source.id,
                    chunk_index=0,
                    content="此来源不属于当前项目。",
                    metadata_json={},
                ),
            ]
        )
        db.commit()

    active_user = {"value": users["owner"]}

    async def override_require_auth() -> CurrentUser:
        return _current(active_user["value"])

    def override_get_db():
        with SessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_auth] = override_require_auth
    try:
        yield TestClient(app), SessionLocal, users, project, lambda user: active_user.update(value=user)
    finally:
        app.dependency_overrides.clear()


def _project_memory_payload(project_id: str, *, source_id: str = "chunk-deployment") -> dict[str, object]:
    return {
        "scope": "project_shared",
        "project_id": project_id,
        "kind": "fact",
        "title": "部署约束",
        "body_markdown": "投标方案需要支持私有化部署。",
        "citations": [
            {
                "source_type": "knowledge_chunk",
                "source_id": source_id,
                "label": "技术规范，第 3 节",
            }
        ],
    }


def _project_graph_memory_payload(
    project_id: str,
    *,
    graph_source_id: str = "chunk-deployment",
) -> dict[str, object]:
    return {
        "scope": "project_shared",
        "project_id": project_id,
        "kind": "entity_note",
        "title": "私有化部署关系",
        "body_markdown": "私有化部署要求应在投标方案中响应。",
        "citations": [
            {
                "source_type": "knowledge_chunk",
                "source_id": "chunk-deployment",
                "label": "技术规范，第 3 节",
            }
        ],
        "structured_data_json": {
            "memory_graph_proposal": {
                "schema_version": "bidpilot.memory-graph/v1",
                "entities": [
                    {
                        "local_id": "deployment",
                        "canonical_name": "私有化部署",
                        "entity_type": "requirement",
                        "evidence_refs": [{"source_type": "knowledge_chunk", "source_id": graph_source_id}],
                    },
                    {
                        "local_id": "response",
                        "canonical_name": "投标方案",
                        "entity_type": "deliverable",
                        "evidence_refs": [{"source_type": "knowledge_chunk", "source_id": graph_source_id}],
                    },
                ],
                "relations": [
                    {
                        "subject_local_id": "deployment",
                        "predicate": "requires",
                        "object_local_id": "response",
                        "evidence_refs": [{"source_type": "knowledge_chunk", "source_id": graph_source_id}],
                    }
                ],
            }
        },
    }


@pytest.mark.parametrize("source_id", ["chunk-does-not-exist", "chunk-foreign"])
def test_project_memory_rejects_fabricated_or_cross_project_citations(memory_client, source_id: str) -> None:
    client, _SessionLocal, users, project, set_user = memory_client
    set_user(users["contributor"])

    response = client.post("/memory", json=_project_memory_payload(project.id, source_id=source_id))

    assert response.status_code == 422
    assert response.json()["detail"] == "Memory citation is not valid for this project"


def test_project_graph_memory_proposal_requires_server_canonical_evidence(memory_client) -> None:
    client, _SessionLocal, users, project, set_user = memory_client
    set_user(users["contributor"])

    accepted = client.post("/memory", json=_project_graph_memory_payload(project.id))
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["status"] == "proposed"
    graph_proposal = accepted.json()["graph_proposal"]
    assert graph_proposal["schema_version"] == "bidpilot.memory-graph/v1"
    assert [(entity["canonical_name"], entity["entity_type"]) for entity in graph_proposal["entities"]] == [
        ("私有化部署", "requirement"),
        ("投标方案", "deliverable"),
    ]
    assert all(entity["evidence_labels"] == ["技术规范.docx · 片段 1"] for entity in graph_proposal["entities"])
    assert all(entity["review_status"] == "pending" for entity in graph_proposal["entities"])
    assert all(entity["item_id"].startswith("gri_") for entity in graph_proposal["entities"])
    assert graph_proposal["relations"] == [
        {
            "item_id": graph_proposal["relations"][0]["item_id"],
            "subject": "私有化部署",
            "predicate": "requires",
            "object": "投标方案",
            "evidence_labels": ["技术规范.docx · 片段 1"],
            "review_status": "pending",
            "review_note": None,
        }
    ]
    assert graph_proposal["relations"][0]["item_id"].startswith("gri_")

    rejected = client.post(
        "/memory",
        json=_project_graph_memory_payload(project.id, graph_source_id="chunk-forged"),
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"] == "Memory graph proposal references unavailable evidence"

    missing_evidence = _project_graph_memory_payload(project.id)
    missing_evidence["citations"] = []
    denied_without_explicit_evidence = client.post("/memory", json=missing_evidence)
    assert denied_without_explicit_evidence.status_code == 422
    assert denied_without_explicit_evidence.json()["detail"] == "Memory graph proposals require explicit project evidence"


def test_graph_proposal_records_per_item_review_before_activation(memory_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, SessionLocal, users, project, set_user = memory_client
    monkeypatch.setattr("app.retrieval.embedding.get_embedding_profile", lambda: None)

    set_user(users["contributor"])
    proposed = client.post("/memory", json=_project_graph_memory_payload(project.id))
    assert proposed.status_code == 201, proposed.text
    memory_id = proposed.json()["id"]
    graph = proposed.json()["graph_proposal"]

    set_user(users["owner"])
    blocked = client.post(f"/memory/{memory_id}/approve")
    assert blocked.status_code == 409
    assert "Review every entity and relation" in blocked.json()["detail"]

    first_entity = graph["entities"][0]
    reviewed = client.post(
        f"/memory/{memory_id}/graph-review",
        json={"item_id": first_entity["item_id"], "decision": "accepted"},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json() == {
        "item_id": first_entity["item_id"],
        "item_type": "entity",
        "decision": "accepted",
        "decision_note": None,
        "reviewed_at": reviewed.json()["reviewed_at"],
    }
    assert "deployment" not in reviewed.json()["item_id"]
    assert "chunk-deployment" not in reviewed.json()["item_id"]

    for item in [*graph["entities"][1:], *graph["relations"]]:
        accepted = client.post(
            f"/memory/{memory_id}/graph-review",
            json={"item_id": item["item_id"], "decision": "accepted"},
        )
        assert accepted.status_code == 200, accepted.text

    active = client.post(f"/memory/{memory_id}/approve")
    assert active.status_code == 200, active.text
    assert active.json()["status"] == "active"
    assert {entity["review_status"] for entity in active.json()["graph_proposal"]["entities"]} == {"accepted"}
    assert {relation["review_status"] for relation in active.json()["graph_proposal"]["relations"]} == {"accepted"}

    frozen = client.post(
        f"/memory/{memory_id}/graph-review",
        json={"item_id": first_entity["item_id"], "decision": "rejected"},
    )
    assert frozen.status_code == 409
    assert frozen.json()["detail"] == "Only proposed graph items can be reviewed"

    with SessionLocal() as db:
        events = db.query(MemoryEvent).filter_by(memory_record_id=memory_id).all()
        assert [event.event_type for event in events] == [
            "memory.created",
            "memory.graph_item_reviewed",
            "memory.graph_item_reviewed",
            "memory.graph_item_reviewed",
            "memory.approved",
            "memory.embedding_deferred",
        ]
        assert db.query(MemoryEntity).filter_by(memory_record_id=memory_id).count() == 0
        assert db.query(MemoryRelation).filter_by(memory_record_id=memory_id).count() == 0


def test_graph_proposal_cannot_activate_after_its_evidence_links_are_removed(
    memory_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, SessionLocal, users, project, set_user = memory_client
    monkeypatch.setattr("app.retrieval.embedding.get_embedding_profile", lambda: None)

    set_user(users["contributor"])
    proposed = client.post("/memory", json=_project_graph_memory_payload(project.id))
    assert proposed.status_code == 201, proposed.text
    memory_id = proposed.json()["id"]
    graph = proposed.json()["graph_proposal"]

    set_user(users["owner"])
    for item in [*graph["entities"], *graph["relations"]]:
        reviewed = client.post(
            f"/memory/{memory_id}/graph-review",
            json={"item_id": item["item_id"], "decision": "accepted"},
        )
        assert reviewed.status_code == 200, reviewed.text

    with SessionLocal() as db:
        link = db.query(MemoryEvidenceLink).filter_by(memory_record_id=memory_id).one()
        db.delete(link)
        db.commit()

    blocked = client.post(f"/memory/{memory_id}/approve")
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "Graph proposal evidence is no longer valid; regenerate it"


def test_invalid_stored_graph_payload_cannot_bypass_activation_gate(memory_client) -> None:
    client, SessionLocal, users, project, set_user = memory_client
    with SessionLocal() as db:
        invalid = MemoryRecord(
            org_id=project.org_id,
            project_id=project.id,
            scope="project_shared",
            kind="entity_note",
            status="proposed",
            title="损坏图谱提案",
            body_markdown="该载荷不符合图谱结构。",
            structured_data_json={"memory_graph_proposal": {"entities": []}},
            retrieval_text="损坏图谱提案",
            origin="system",
            created_by_actor_type="system",
            created_by_actor_id="memory-graph-proposer",
        )
        db.add(invalid)
        db.commit()
        memory_id = invalid.id

    set_user(users["owner"])
    blocked = client.post(f"/memory/{memory_id}/approve")
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "Graph proposal is invalid; regenerate it before approval"


def test_worker_graph_proposal_cannot_activate_after_source_snapshot_changes(
    memory_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.memory.service import _memory_graph_snapshot_fingerprint

    client, SessionLocal, users, project, set_user = memory_client
    monkeypatch.setattr("app.retrieval.embedding.get_embedding_profile", lambda: None)
    graph_payload = _project_graph_memory_payload(project.id)["structured_data_json"]
    assert isinstance(graph_payload, dict)

    with SessionLocal() as db:
        source = MemoryRecord(
            org_id=project.org_id,
            project_id=project.id,
            scope="project_shared",
            kind="summary",
            status="active",
            title="原始已批准知识",
            body_markdown="私有化部署要求应在投标方案中响应。",
            retrieval_text="私有化部署要求应在投标方案中响应。",
            origin="system",
            created_by_actor_type="system",
            created_by_actor_id="worker",
        )
        db.add(source)
        db.flush()
        source_link = MemoryEvidenceLink(
            memory_record_id=source.id,
            source_type="knowledge_chunk",
            source_id="chunk-deployment",
            label="技术规范.docx · 片段 1",
            locator_json={"chunk_index": 0},
        )
        db.add(source_link)
        db.flush()
        proposal = MemoryRecord(
            org_id=project.org_id,
            project_id=project.id,
            scope="project_shared",
            kind="entity_note",
            status="proposed",
            title="原始已批准知识 · 实体关系提案",
            body_markdown="待审核实体关系提案。",
            structured_data_json={
                **graph_payload,
                "source_memory_record_id": source.id,
                "graph_policy_version": "memory-graph-proposer-v1",
            },
            content_fingerprint=_memory_graph_snapshot_fingerprint(source, [source_link]),
            retrieval_text="实体关系提案",
            origin="system",
            created_by_actor_type="system",
            created_by_actor_id="memory-graph-proposer",
        )
        db.add(proposal)
        db.flush()
        db.add(
            MemoryEvidenceLink(
                memory_record_id=proposal.id,
                source_type=source_link.source_type,
                source_id=source_link.source_id,
                evidence_role="derived_from",
                label=source_link.label,
                locator_json=source_link.locator_json,
            )
        )
        db.commit()
        proposal_id = proposal.id
        source_id = source.id

    set_user(users["owner"])
    records = client.get(
        "/memory",
        params={"project_id": project.id, "scope": "project_shared", "include_proposed": "true"},
    )
    assert records.status_code == 200, records.text
    graph = next(record["graph_proposal"] for record in records.json() if record["id"] == proposal_id)
    for item in [*graph["entities"], *graph["relations"]]:
        reviewed = client.post(
            f"/memory/{proposal_id}/graph-review",
            json={"item_id": item["item_id"], "decision": "accepted"},
        )
        assert reviewed.status_code == 200, reviewed.text

    with SessionLocal() as db:
        source = db.get(MemoryRecord, source_id)
        assert source is not None
        source.body_markdown = "来源资料已修订，原关系不再可用。"
        db.commit()

    blocked = client.post(f"/memory/{proposal_id}/approve")
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "Graph proposal source changed; regenerate it before approval"


def test_contributor_can_propose_but_owner_controls_activation(memory_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _SessionLocal, users, project, set_user = memory_client
    monkeypatch.setattr("app.retrieval.embedding.get_embedding_profile", lambda: None)

    set_user(users["contributor"])
    proposed = client.post("/memory", json=_project_memory_payload(project.id))
    assert proposed.status_code == 201, proposed.text
    assert proposed.json()["status"] == "proposed"
    assert proposed.json()["citations"] == [
        {
            "source_type": "knowledge_chunk",
            "source_id": "chunk-deployment",
            "label": "技术规范.docx · 片段 1",
            "locator_json": {"source_document_id": "source-memory", "chunk_index": 0},
        }
    ]
    memory_id = proposed.json()["id"]

    denied = client.post(f"/memory/{memory_id}/approve")
    assert denied.status_code == 403

    set_user(users["owner"])
    approved = client.post(f"/memory/{memory_id}/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "active"

    set_user(users["viewer"])
    visible = client.get("/memory", params={"project_id": project.id})
    assert visible.status_code == 200, visible.text
    assert [record["id"] for record in visible.json()] == [memory_id]

    set_user(users["outsider"])
    hidden = client.get("/memory", params={"project_id": project.id})
    assert hidden.status_code == 404


def test_project_memory_can_be_edited_or_returned_with_review_history(
    memory_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _SessionLocal, users, project, set_user = memory_client
    monkeypatch.setattr("app.retrieval.embedding.get_embedding_profile", lambda: None)

    set_user(users["contributor"])
    proposed = client.post("/memory", json=_project_memory_payload(project.id))
    assert proposed.status_code == 201, proposed.text
    memory_id = proposed.json()["id"]

    set_user(users["owner"])
    edited = client.patch(
        f"/memory/{memory_id}",
        json={
            "title": "修订后的部署约束",
            "body_markdown": "投标方案必须支持私有化部署，并说明交付边界。",
            "expires_at": "2026-12-31T23:59:59",
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["title"] == "修订后的部署约束"
    assert edited.json()["expires_at"].startswith("2026-12-31")

    returned = client.post(
        f"/memory/{memory_id}/reject",
        json={"reason": "请补充交付边界的依据。"},
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["status"] == "rejected"

    hidden_from_active_list = client.get(
        "/memory",
        params={"project_id": project.id, "scope": "project_shared", "include_proposed": "true"},
    )
    assert hidden_from_active_list.status_code == 200, hidden_from_active_list.text
    assert memory_id not in {record["id"] for record in hidden_from_active_list.json()}

    history = client.get(
        "/memory",
        params={
            "project_id": project.id,
            "scope": "project_shared",
            "include_proposed": "true",
            "include_history": "true",
        },
    )
    assert history.status_code == 200, history.text
    assert next(record for record in history.json() if record["id"] == memory_id)["status"] == "rejected"


def test_active_project_memory_supports_expiry_and_superseding(
    memory_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, SessionLocal, users, project, set_user = memory_client
    monkeypatch.setattr("app.retrieval.embedding.get_embedding_profile", lambda: None)

    set_user(users["contributor"])
    proposed = client.post("/memory", json=_project_memory_payload(project.id))
    assert proposed.status_code == 201, proposed.text
    memory_id = proposed.json()["id"]

    set_user(users["owner"])
    approved = client.post(f"/memory/{memory_id}/approve")
    assert approved.status_code == 200, approved.text

    changed_expiry = client.patch(
        f"/memory/{memory_id}",
        json={"expires_at": "2027-01-31T23:59:59"},
    )
    assert changed_expiry.status_code == 200, changed_expiry.text
    assert changed_expiry.json()["expires_at"].startswith("2027-01-31")

    rejected_content_edit = client.patch(
        f"/memory/{memory_id}",
        json={"body_markdown": "不应该直接覆盖已经生效的内容。"},
    )
    assert rejected_content_edit.status_code == 409

    replacement = client.post(
        f"/memory/{memory_id}/supersede",
        json={
            "title": "新的部署约束",
            "body_markdown": "新的投标方案仍需支持私有化部署。",
            "expires_at": "2027-06-30T23:59:59",
        },
    )
    assert replacement.status_code == 200, replacement.text
    assert replacement.json()["status"] == "proposed"
    assert replacement.json()["supersedes_id"] == memory_id
    assert replacement.json()["citations"] == approved.json()["citations"]

    with SessionLocal() as db:
        old_record = db.get(MemoryRecord, memory_id)
        assert old_record is not None
        assert old_record.status == "superseded"


def test_private_memory_is_owner_scoped_and_tombstoned_on_delete(memory_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, SessionLocal, users, _project, set_user = memory_client
    monkeypatch.setattr("app.retrieval.embedding.get_embedding_profile", lambda: None)

    private = client.post(
        "/memory",
        json={
            "scope": "user_private",
            "kind": "preference",
            "title": "写作偏好",
            "body_markdown": "默认先给出结论，再补充依据。",
        },
    )
    assert private.status_code == 201, private.text
    assert private.json()["status"] == "active"
    assert private.json()["citations"] == [
        {
            "source_type": "human_decision",
            "source_id": users["owner"].id,
            "label": "用户明确写入",
            "locator_json": None,
        }
    ]
    memory_id = private.json()["id"]

    set_user(users["contributor"])
    other_user_view = client.get("/memory", params={"scope": "user_private"})
    assert other_user_view.status_code == 200
    assert other_user_view.json() == []

    set_user(users["owner"])
    deleted = client.delete(f"/memory/{memory_id}")
    assert deleted.status_code == 204
    assert client.get("/memory", params={"scope": "user_private"}).json() == []

    with SessionLocal() as db:
        events = db.query(MemoryEvent).filter(MemoryEvent.memory_record_id == memory_id).all()
        assert [event.event_type for event in events] == [
            "memory.created",
            "memory.embedding_deferred",
            "memory.deleted",
        ]


def test_personal_memory_control_surface_lists_and_clears_both_ledgers(
    memory_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, SessionLocal, users, _project, set_user = memory_client
    monkeypatch.setattr("app.retrieval.embedding.get_embedding_profile", lambda: None)
    set_user(users["owner"])

    local = client.post(
        "/memory",
        json={
            "scope": "user_private",
            "kind": "preference",
            "title": "回答格式",
            "body_markdown": "先给结论，再补充依据。",
        },
    )
    assert local.status_code == 201, local.text

    provider_memory = Mem0ProfileMemory(
        memory_id="profile-1",
        text="使用中文回答。",
        score=0.9,
        categories=("preferences",),
    )
    monkeypatch.setattr("app.memory.service.mem0_enabled", lambda: True)
    monkeypatch.setattr(
        "app.memory.service.list_profile_memory",
        lambda *, user_id, org_id: [provider_memory],
    )
    deleted_provider_ids: list[str] = []
    monkeypatch.setattr(
        "app.memory.service.delete_profile_memory_item",
        lambda *, memory_id: deleted_provider_ids.append(memory_id) or {"status": "deleted"},
    )
    monkeypatch.setattr(
        "app.memory.service.delete_profile_memory",
        lambda *, user_id, org_id: {"status": "deleted"},
    )

    listed = client.get("/memory/profile")
    assert listed.status_code == 200, listed.text
    assert listed.json()["enabled"] is True
    assert listed.json()["local_records"][0]["title"] == "回答格式"
    assert listed.json()["profile_records"] == [
        {
            "id": "profile-1",
            "text": "使用中文回答。",
            "score": 0.9,
            "categories": ["preferences"],
        }
    ]

    deleted = client.delete("/memory/profile/profile-1")
    assert deleted.status_code == 204
    assert deleted_provider_ids == ["profile-1"]

    cleared = client.delete("/memory/profile")
    assert cleared.status_code == 200, cleared.text
    assert cleared.json() == {"local_deleted_count": 1, "provider_status": "deleted"}
    assert client.get("/memory", params={"scope": "user_private"}).json() == []

    with SessionLocal() as db:
        assert db.query(MemoryRecord).filter_by(owner_user_id=users["owner"].id, status="active").count() == 0


def test_project_private_memory_requires_the_authorized_project_scope(memory_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _SessionLocal, users, project, set_user = memory_client
    monkeypatch.setattr("app.retrieval.embedding.get_embedding_profile", lambda: None)
    set_user(users["owner"])

    global_private = client.post(
        "/memory",
        json={
            "scope": "user_private",
            "kind": "preference",
            "title": "全局偏好",
            "body_markdown": "默认先给结论。",
        },
    )
    project_private = client.post(
        "/memory",
        json={
            "scope": "user_private",
            "project_id": project.id,
            "kind": "preference",
            "title": "项目偏好",
            "body_markdown": "本项目优先使用技术规范原文。",
        },
    )
    assert global_private.status_code == 201, global_private.text
    assert project_private.status_code == 201, project_private.text

    unscoped = client.get("/memory", params={"scope": "user_private"})
    assert unscoped.status_code == 200, unscoped.text
    assert [record["id"] for record in unscoped.json()] == [global_private.json()["id"]]

    scoped = client.get(
        "/memory",
        params={"scope": "user_private", "project_id": project.id},
    )
    assert scoped.status_code == 200, scoped.text
    assert [record["id"] for record in scoped.json()] == [project_private.json()["id"]]

    set_user(users["viewer"])
    other_member = client.get(
        "/memory",
        params={"scope": "user_private", "project_id": project.id},
    )
    assert other_member.status_code == 200, other_member.text
    assert other_member.json() == []

    # The default project Wiki view may include its caller's personal record,
    # but must never turn a teammate's private preference into shared data.
    unscoped_other_member = client.get("/memory", params={"project_id": project.id})
    assert unscoped_other_member.status_code == 200, unscoped_other_member.text
    assert unscoped_other_member.json() == []


def test_memory_portfolio_only_exposes_authorized_project_shared_metadata(memory_client) -> None:
    client, SessionLocal, users, project, set_user = memory_client
    with SessionLocal() as db:
        hidden_project = Project(
            id="project-memory-hidden",
            org_id=project.org_id,
            slug="memory-hidden-bid",
            name="Hidden Memory Bid",
            scenario_package="bidpilot",
        )
        db.add(hidden_project)
        db.flush()
        db.add(ProjectMember(project_id=hidden_project.id, user_id=users["owner"].id, role="owner"))
        db.add_all(
            [
                MemoryRecord(
                    org_id=project.org_id,
                    project_id=project.id,
                    scope="project_shared",
                    kind="fact",
                    status="active",
                    title="Shared deployment fact",
                    body_markdown="Source-backed shared knowledge.",
                    retrieval_text="shared deployment fact",
                    origin="user",
                    created_by_actor_type="user",
                    created_by_actor_id=users["owner"].id,
                ),
                MemoryRecord(
                    org_id=project.org_id,
                    project_id=project.id,
                    scope="project_shared",
                    kind="fact",
                    status="active",
                    title="Expired shared fact",
                    body_markdown="Expired knowledge must not be portfolio-ready.",
                    retrieval_text="expired shared fact",
                    origin="user",
                    created_by_actor_type="user",
                    created_by_actor_id=users["owner"].id,
                    expires_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1),
                ),
                MemoryRecord(
                    org_id=project.org_id,
                    project_id=project.id,
                    scope="project_shared",
                    kind="fact",
                    status="proposed",
                    title="Proposed shared fact",
                    body_markdown="Awaiting a reviewer.",
                    retrieval_text="proposed shared fact",
                    origin="user",
                    created_by_actor_type="user",
                    created_by_actor_id=users["contributor"].id,
                ),
                MemoryRecord(
                    org_id=project.org_id,
                    project_id=project.id,
                    owner_user_id=users["owner"].id,
                    scope="user_private",
                    kind="preference",
                    status="active",
                    title="PRIVATE_PORTFOLIO_LEAK",
                    body_markdown="Never render this in a team portfolio.",
                    retrieval_text="private portfolio preference",
                    origin="user",
                    created_by_actor_type="user",
                    created_by_actor_id=users["owner"].id,
                ),
                MemoryRecord(
                    org_id=project.org_id,
                    project_id=hidden_project.id,
                    scope="project_shared",
                    kind="fact",
                    status="active",
                    title="Hidden project fact",
                    body_markdown="Only the owner can discover this project.",
                    retrieval_text="hidden project fact",
                    origin="user",
                    created_by_actor_type="user",
                    created_by_actor_id=users["owner"].id,
                ),
                MemoryCompilationRun(
                    org_id=project.org_id,
                    project_id=project.id,
                    initiated_by_user_id=users["owner"].id,
                    status="succeeded",
                    input_source_ids_json=[],
                    input_memory_ids_json=[],
                    policy_version="memory-compiler-v1",
                ),
            ]
        )
        db.commit()

    set_user(users["viewer"])
    viewer_response = client.get("/memory/portfolio")
    assert viewer_response.status_code == 200, viewer_response.text
    assert viewer_response.json() == [
        {
            "project_id": project.id,
            "project_name": project.name,
            "active_shared_count": 1,
            "proposed_shared_count": None,
            "latest_shared_memory_at": viewer_response.json()[0]["latest_shared_memory_at"],
            "latest_compilation_status": "succeeded",
            "latest_compilation_at": viewer_response.json()[0]["latest_compilation_at"],
        }
    ]
    assert "PRIVATE_PORTFOLIO_LEAK" not in viewer_response.text
    assert "Hidden Memory Bid" not in viewer_response.text

    set_user(users["owner"])
    owner_response = client.get("/memory/portfolio")
    assert owner_response.status_code == 200, owner_response.text
    owner_rows = {item["project_id"]: item for item in owner_response.json()}
    assert owner_rows[project.id]["proposed_shared_count"] == 1
    assert owner_rows[hidden_project.id]["active_shared_count"] == 1
    assert "PRIVATE_PORTFOLIO_LEAK" not in owner_response.text


def test_evidence_map_is_project_shared_and_source_redacted(memory_client) -> None:
    client, SessionLocal, users, project, set_user = memory_client
    with SessionLocal() as db:
        active_record = MemoryRecord(
            org_id=project.org_id,
            project_id=project.id,
            scope="project_shared",
            kind="fact",
            status="active",
            title="Shared deployment fact",
            body_markdown="This body is visible in the ledger, not the map response.",
            retrieval_text="shared deployment fact",
            origin="user",
            created_by_actor_type="user",
            created_by_actor_id=users["owner"].id,
        )
        proposed_record = MemoryRecord(
            org_id=project.org_id,
            project_id=project.id,
            scope="project_shared",
            kind="risk",
            status="proposed",
            title="PROPOSED_GRAPH_LEAK",
            body_markdown="A proposal is not part of the active Evidence Map.",
            retrieval_text="proposed graph leak",
            origin="user",
            created_by_actor_type="user",
            created_by_actor_id=users["contributor"].id,
        )
        private_record = MemoryRecord(
            org_id=project.org_id,
            project_id=project.id,
            owner_user_id=users["owner"].id,
            scope="user_private",
            kind="preference",
            status="active",
            title="PRIVATE_GRAPH_LEAK",
            body_markdown="Personal preferences must never enter the team map.",
            retrieval_text="private graph leak",
            origin="user",
            created_by_actor_type="user",
            created_by_actor_id=users["owner"].id,
        )
        expired_record = MemoryRecord(
            org_id=project.org_id,
            project_id=project.id,
            scope="project_shared",
            kind="fact",
            status="active",
            title="EXPIRED_GRAPH_LEAK",
            body_markdown="Expired knowledge must not appear in the map.",
            retrieval_text="expired graph leak",
            origin="user",
            created_by_actor_type="user",
            created_by_actor_id=users["owner"].id,
            expires_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1),
        )
        db.add_all([active_record, proposed_record, private_record, expired_record])
        db.flush()
        db.add_all(
            [
                MemoryEvidenceLink(
                    memory_record_id=active_record.id,
                    source_type="knowledge_chunk",
                    source_id="chunk-deployment",
                    label="技术规范.docx · 片段 1",
                ),
                MemoryEvidenceLink(
                    memory_record_id=active_record.id,
                    source_type="requirement_item",
                    source_id="requirement-deployment",
                    label="私有化部署要求",
                ),
                MemoryEvidenceLink(
                    memory_record_id=proposed_record.id,
                    source_type="knowledge_chunk",
                    source_id="chunk-deployment",
                    label="技术规范.docx · 片段 1",
                ),
            ]
        )
        db.commit()

    set_user(users["viewer"])
    response = client.get("/memory/evidence-map", params={"project_id": project.id})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["project_id"] == project.id
    assert payload["truncated"] is False
    assert len(payload["nodes"]) == 3
    assert len(payload["edges"]) == 2
    assert {node["label"] for node in payload["nodes"]} == {
        "Shared deployment fact",
        "技术规范.docx · 片段 1",
        "私有化部署要求",
    }
    assert {node["node_type"] for node in payload["nodes"]} == {"memory", "source"}
    assert all(edge["predicate"] == "cites" for edge in payload["edges"])
    assert all(edge["source"] in {node["id"] for node in payload["nodes"]} for edge in payload["edges"])
    assert all(edge["target"] in {node["id"] for node in payload["nodes"]} for edge in payload["edges"])
    assert "chunk-deployment" not in response.text
    assert "PRIVATE_GRAPH_LEAK" not in response.text
    assert "PROPOSED_GRAPH_LEAK" not in response.text
    assert "EXPIRED_GRAPH_LEAK" not in response.text
    assert "This body is visible" not in response.text

    constrained = client.get(
        "/memory/evidence-map",
        params={"project_id": project.id, "max_sources": 1},
    )
    assert constrained.status_code == 200, constrained.text
    assert constrained.json()["truncated"] is True
    assert len([node for node in constrained.json()["nodes"] if node["node_type"] == "source"]) == 1
    assert len(constrained.json()["edges"]) == 1

    set_user(users["outsider"])
    denied = client.get("/memory/evidence-map", params={"project_id": project.id})
    assert denied.status_code == 404


def test_approval_queues_memory_index_and_records_official_usage(memory_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, SessionLocal, users, project, set_user = memory_client
    dispatched: list[tuple[str, list[list[str]]]] = []
    monkeypatch.setattr(
        "app.retrieval.embedding.get_embedding_profile",
        lambda: type("Profile", (), {"identifier": "embedding-test-v1"})(),
    )
    monkeypatch.setattr(
        "app.memory.service.celery.send_task",
        lambda task_name, args: dispatched.append((task_name, args)),
    )

    set_user(users["contributor"])
    proposed = client.post("/memory", json=_project_memory_payload(project.id))
    assert proposed.status_code == 201, proposed.text

    set_user(users["owner"])
    approved = client.post(f"/memory/{proposed.json()['id']}/approve")
    assert approved.status_code == 200, approved.text

    assert dispatched == [("worker.index_memory_records", [[proposed.json()["id"]]])]
    with SessionLocal() as db:
        usage = db.query(UsageEvent).filter_by(
            user_id=users["owner"].id,
            event_type=EMBEDDING_INDEX_STARTED,
        ).one()
        assert usage.provider_source == ProviderSource.OFFICIAL.value
        assert usage.metadata_json == {"memory_record_id": proposed.json()["id"], "action": "index_memory"}
        events = db.query(MemoryEvent).filter_by(memory_record_id=proposed.json()["id"]).all()
        assert [event.event_type for event in events] == [
            "memory.created",
            "memory.approved",
            "memory.embedding_index_requested",
        ]


def test_approval_defers_memory_vector_index_without_blocking_the_ledger(memory_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, SessionLocal, users, project, set_user = memory_client
    monkeypatch.setattr(
        "app.retrieval.embedding.get_embedding_profile",
        lambda: type("Profile", (), {"identifier": "embedding-test-v1"})(),
    )
    dispatched: list[tuple[str, list[list[str]]]] = []
    monkeypatch.setattr(
        "app.memory.service.celery.send_task",
        lambda task_name, args: dispatched.append((task_name, args)),
    )
    with SessionLocal() as db:
        for _ in range(5):
            record_usage_event(
                db,
                user_id=users["owner"].id,
                org_id=users["owner"].org_id,
                project_id=project.id,
                event_type=EMBEDDING_INDEX_STARTED,
                provider_source=ProviderSource.OFFICIAL,
            )
        db.commit()

    set_user(users["contributor"])
    proposed = client.post("/memory", json=_project_memory_payload(project.id))
    assert proposed.status_code == 201, proposed.text

    set_user(users["owner"])
    approved = client.post(f"/memory/{proposed.json()['id']}/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "active"
    assert dispatched == []

    with SessionLocal() as db:
        events = db.query(MemoryEvent).filter_by(memory_record_id=proposed.json()["id"]).all()
        assert events[-1].event_type == "memory.embedding_deferred"
        assert events[-1].payload_json == {"reason": "official_indexing_quota_exhausted"}


def test_only_project_approvers_can_queue_bid_wiki_compilation(memory_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, SessionLocal, users, project, set_user = memory_client
    with SessionLocal() as db:
        bundle = Bundle(project_id=project.id, label="招标材料", source_type="upload", ingest_status="ingested")
        db.add(bundle)
        db.flush()
        source = SourceDocument(
            bundle_id=bundle.id,
            storage_key="uploads/wiki.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            checksum="wiki-test",
            original_filename="招标技术规范.docx",
            parse_status="parsed",
        )
        db.add(source)
        db.commit()
        bundle_id = bundle.id

    dispatched: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        "app.memory.service.celery.send_task",
        lambda task_name, args: dispatched.append((task_name, args)),
    )

    set_user(users["contributor"])
    denied = client.post("/memory/compile", json={"project_id": project.id, "bundle_id": bundle_id})
    assert denied.status_code == 403

    set_user(users["owner"])
    queued = client.post("/memory/compile", json={"project_id": project.id, "bundle_id": bundle_id})
    assert queued.status_code == 201, queued.text
    payload = queued.json()
    assert payload["status"] == "queued"
    assert payload["input_source_count"] == 1
    assert dispatched == [("worker.compile_bid_wiki", [payload["id"]])]

    with SessionLocal() as db:
        run = db.get(MemoryCompilationRun, payload["id"])
        assert run is not None
        assert run.project_id == project.id
        assert run.input_source_ids_json


def test_owner_can_queue_source_bound_memory_graph_extraction(memory_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, SessionLocal, users, project, set_user = memory_client
    monkeypatch.setattr("app.retrieval.embedding.get_embedding_profile", lambda: None)
    monkeypatch.setattr("app.memory.service.check_workflow_quota", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.memory.service.reserve_workflow_model_tokens", lambda *_args, **_kwargs: None)
    dispatched: list[str] = []
    monkeypatch.setattr("app.memory.service.request_task_outbox_dispatch", lambda event_id: dispatched.append(event_id))

    set_user(users["contributor"])
    proposed = client.post("/memory", json=_project_memory_payload(project.id))
    assert proposed.status_code == 201, proposed.text

    set_user(users["owner"])
    approved = client.post(f"/memory/{proposed.json()['id']}/approve")
    assert approved.status_code == 200, approved.text

    queued = client.post(
        "/memory/graph-extractions",
        json={"project_id": project.id, "memory_record_id": approved.json()["id"], "reasoning_effort": "high"},
    )
    assert queued.status_code == 202, queued.text
    payload = queued.json()
    assert payload["status"] == "queued"
    assert payload["memory_record_id"] == approved.json()["id"]
    assert len(dispatched) == 1

    with SessionLocal() as db:
        run = db.get(ExecutionRun, payload["run_id"])
        assert run is not None
        assert run.run_type == "memory_graph_extraction"
        assert run.input_json["memory_record_id"] == approved.json()["id"]
        assert run.input_json["graph_policy_version"] == "memory-graph-proposer-v1"
        runtime = db.get(RuntimeRun, payload["runtime_run_id"])
        assert runtime is not None
        assert runtime.engine == "memory_graph_extraction"
        assert runtime.execution_run_id == run.id
        usage = db.query(UsageEvent).filter_by(execution_run_id=run.id).one()
        assert usage.event_type == "workflow_draft_started"
        assert usage.provider_source == ProviderSource.OFFICIAL.value

    same_snapshot = client.post(
        "/memory/graph-extractions",
        json={"project_id": project.id, "memory_record_id": approved.json()["id"], "reasoning_effort": "high"},
    )
    assert same_snapshot.status_code == 202, same_snapshot.text
    assert same_snapshot.json()["run_id"] == payload["run_id"]
    assert same_snapshot.json()["reused"] is True
    assert len(dispatched) == 1

    with SessionLocal() as db:
        run = db.get(ExecutionRun, payload["run_id"])
        assert run is not None
        run.status = "failed"
        outbox = db.query(TaskOutboxEvent).filter_by(execution_run_id=run.id).one()
        outbox.status = "failed"
        db.commit()

    retried = client.post(
        "/memory/graph-extractions",
        json={"project_id": project.id, "memory_record_id": approved.json()["id"], "reasoning_effort": "high"},
    )
    assert retried.status_code == 202, retried.text
    assert retried.json()["run_id"] != payload["run_id"]
    assert retried.json()["reused"] is False
    assert len(dispatched) == 2

    with SessionLocal() as db:
        retry_run = db.get(ExecutionRun, retried.json()["run_id"])
        assert retry_run is not None
        assert retry_run.parent_execution_run_id == payload["run_id"]
        assert retry_run.attempt_number == 2
        outbox = db.query(TaskOutboxEvent).filter_by(execution_run_id=retry_run.id).one()
        assert outbox.status == "pending"

    set_user(users["contributor"])
    denied = client.post(
        "/memory/graph-extractions",
        json={"project_id": project.id, "memory_record_id": approved.json()["id"]},
    )
    assert denied.status_code == 403


def test_memory_graph_extraction_does_not_commit_partial_control_plane_state(
    memory_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, SessionLocal, users, project, set_user = memory_client
    monkeypatch.setattr("app.retrieval.embedding.get_embedding_profile", lambda: None)
    monkeypatch.setattr("app.memory.service.check_workflow_quota", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.memory.service.reserve_workflow_model_tokens", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.memory.service.record_audit_event", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("audit unavailable")))

    set_user(users["contributor"])
    proposed = client.post("/memory", json=_project_memory_payload(project.id))
    assert proposed.status_code == 201, proposed.text

    set_user(users["owner"])
    approved = client.post(f"/memory/{proposed.json()['id']}/approve")
    assert approved.status_code == 200, approved.text

    with TestClient(app, raise_server_exceptions=False) as no_raise_client:
        failed = no_raise_client.post(
            "/memory/graph-extractions",
            json={"project_id": project.id, "memory_record_id": approved.json()["id"]},
        )
    assert failed.status_code == 500

    with SessionLocal() as db:
        assert db.query(ExecutionRun).filter_by(run_type="memory_graph_extraction").count() == 0
        assert db.query(RuntimeRun).filter_by(engine="memory_graph_extraction").count() == 0
        assert db.query(TaskOutboxEvent).filter_by(task_name="worker.extract_memory_graph").count() == 0
        assert db.query(UsageEvent).filter_by(event_type="workflow_draft_started").count() == 0
