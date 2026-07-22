from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.schemas import CurrentUser
from app.auth.service import _hash_password, require_auth
from app.db import Base, get_db
from app.main import app
from app.models import (
    Bundle,
    Deliverable,
    DeliverableSection,
    ExecutionRun,
    KnowledgeChunk,
    Organization,
    OrganizationMembership,
    ParsedAsset,
    Project,
    ProjectMember,
    ReviewThread,
    SectionVersion,
    SourceDocument,
    User,
)
from contracts import EmbeddingOutcome, EmbeddingOutcomeStatus


def _current(user: User) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        plan="professional",
        email_verified=True,
        disabled=False,
        org_id=user.org_id,
        org_slug="acme",
    )


@pytest.fixture()
def resource_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as db:
        org = Organization(id="org-acme", slug="acme", name="Acme")
        outsider_org = Organization(id="org-other", slug="other", name="Other")
        project = Project(
            id="project-alpha",
            org_id=org.id,
            slug="alpha",
            name="Alpha Bid",
            scenario_package="bidpilot",
        )
        users = {
            role: User(
                id=f"user-{role}",
                org_id=org.id,
                email=f"{role}@acme.test",
                display_name=role.title(),
                password_hash=_hash_password("Test1234"),
                role="member",
                email_verified=True,
            )
            for role in ("owner", "contributor", "reviewer", "viewer")
        }
        users["outsider"] = User(
            id="user-outsider",
            org_id=outsider_org.id,
            email="outsider@other.test",
            display_name="Outsider",
            password_hash=_hash_password("Test1234"),
            role="member",
            email_verified=True,
        )
        bundle = Bundle(
            id="bundle-alpha",
            project_id=project.id,
            label="Tender package",
            source_type="upload",
        )
        deliverable = Deliverable(
            id="deliverable-alpha",
            project_id=project.id,
            type="proposal",
            title="Proposal",
        )
        section = DeliverableSection(
            id="section-alpha",
            deliverable_id=deliverable.id,
            section_key="technical",
            title="Technical response",
            status="approved",
        )
        run = ExecutionRun(
            id="run-alpha",
            project_id=project.id,
            run_type="draft_section",
            status="awaiting_human",
            input_json={"section_key": "technical"},
        )
        thread = ReviewThread(
            id="thread-alpha",
            deliverable_section_id=section.id,
            status="open",
            opened_by=users["owner"].id,
        )
        document = SourceDocument(
            id="document-alpha",
            bundle_id=bundle.id,
            storage_key="bucket/bundle-alpha/tender.md",
            mime_type="text/markdown",
            checksum="a" * 64,
            original_filename="tender.md",
        )
        asset = ParsedAsset(
            id="asset-alpha",
            source_document_id=document.id,
            parser_name="test-parser",
            parser_version="1",
            content_json={"text": "Tender requirements"},
        )
        chunk = KnowledgeChunk(
            id="chunk-alpha",
            project_id=project.id,
            source_document_id=document.id,
            chunk_index=0,
            content="The response must include a technical approach.",
        )
        version = SectionVersion(
            id="version-alpha",
            deliverable_section_id=section.id,
            version_number=1,
            content_markdown="## Technical approach\n\nApproved draft.",
            created_by_actor="ai",
        )
        db.add_all(
            [
                org,
                outsider_org,
                project,
                *users.values(),
                bundle,
                deliverable,
                section,
                run,
                thread,
                document,
                asset,
                chunk,
                version,
            ]
        )
        db.flush()
        db.add_all(
            [
                OrganizationMembership(
                    org_id=org.id,
                    user_id=users[role].id,
                    role="owner" if role == "owner" else "member",
                )
                for role in ("owner", "contributor", "reviewer", "viewer")
            ]
            + [
                OrganizationMembership(
                    org_id=outsider_org.id,
                    user_id=users["outsider"].id,
                    role="owner",
                )
            ]
        )
        db.add_all(
            [
                ProjectMember(project_id=project.id, user_id=users[role].id, role=role)
                for role in ("owner", "contributor", "reviewer", "viewer")
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
        yield (
            TestClient(app),
            users,
            project,
            bundle,
            run,
            section,
            thread,
            {"document": document, "asset": asset},
            lambda user: active_user.update(value=user),
        )
    finally:
        app.dependency_overrides.clear()


def test_bundle_and_drafting_routes_require_project_capabilities(resource_client) -> None:
    client, users, project, bundle, run, _section, _thread, _resources, set_user = resource_client

    set_user(users["viewer"])
    listed = client.get("/bundles", params={"project_id": project.id})
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [bundle.id]

    set_user(users["reviewer"])
    denied_draft = client.post(
        "/drafting/sections",
        json={"project_id": project.id, "section_key": "technical"},
    )
    assert denied_draft.status_code == 403
    denied_resume = client.post(f"/drafting/runs/{run.id}/resume", json={"decision": "approved"})
    assert denied_resume.status_code == 403

    set_user(users["contributor"])
    with patch("app.drafting.service.request_task_outbox_dispatch") as request_dispatch:
        started = client.post(
            "/drafting/sections",
            json={"project_id": project.id, "section_key": "technical"},
        )
    assert started.status_code == 202, started.text
    assert request_dispatch.called

    set_user(users["outsider"])
    hidden_bundles = client.get("/bundles", params={"project_id": project.id})
    assert hidden_bundles.status_code == 404
    hidden_stream = client.get(f"/drafting/runs/{run.id}/stream")
    assert hidden_stream.status_code == 404


def test_review_routes_require_read_or_review_capabilities(resource_client, monkeypatch) -> None:
    client, users, _project, _bundle, _run, section, thread, _resources, set_user = resource_client
    monkeypatch.setattr("app.review.service.send_review_notification_email", lambda **_kwargs: None)

    set_user(users["viewer"])
    visible_threads = client.get("/review/threads", params={"section_id": section.id})
    assert visible_threads.status_code == 200, visible_threads.text
    assert visible_threads.json()[0]["id"] == thread.id
    denied_comment = client.post(
        "/review/comments",
        json={"thread_id": thread.id, "body": "Viewer cannot comment."},
    )
    assert denied_comment.status_code == 403

    set_user(users["contributor"])
    denied_decision = client.post(
        "/review/decisions",
        json={"section_id": section.id, "decision": "approved"},
    )
    assert denied_decision.status_code == 403

    set_user(users["reviewer"])
    accepted = client.post(
        "/review/comments",
        json={
            "thread_id": thread.id,
            "body": "Reviewer comment.",
            "author_id": users["owner"].id,
        },
    )
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["author_id"] == users["reviewer"].id

    set_user(users["outsider"])
    hidden_comments = client.get(f"/review/threads/{thread.id}/comments")
    assert hidden_comments.status_code == 404


def test_content_and_observability_routes_share_project_access(resource_client, monkeypatch) -> None:
    client, users, project, bundle, run, section, _thread, resources, set_user = resource_client

    monkeypatch.setattr("app.adapters.storage.download_bytes", lambda *_args: b"document-data")
    monkeypatch.setattr(
        "app.retrieval.service.generate_metered_query_embedding",
        lambda **_kwargs: EmbeddingOutcome(
            status=EmbeddingOutcomeStatus.SUCCESS,
            profile_id="test:embedding:1536:bidpilot-lexical-v1",
            vector=[0.1] * 1536,
        ),
    )

    set_user(users["viewer"])
    assert client.get("/deliverables", params={"project_id": project.id}).status_code == 200
    assert client.get(f"/deliverables/{'deliverable-alpha'}/sections").status_code == 200
    assert client.get(f"/execution/runs/{run.id}").status_code == 200
    assert client.get("/execution/runs", params={"project_id": project.id}).status_code == 200
    assert client.get("/versions", params={"section_id": section.id}).status_code == 200
    assert client.get("/documents", params={"bundle_id": bundle.id}).status_code == 200
    assert client.get(f"/documents/{resources['document'].id}/download").status_code == 200
    assert client.get("/parsed-assets", params={"source_document_id": resources["document"].id}).status_code == 200
    assert client.get(f"/parsed-assets/{resources['asset'].id}").status_code == 200
    # Audit routes retain the existing organization-admin guard in addition
    # to project scoping; viewers can inspect project data but not audit logs.
    assert client.get("/audit/events", params={"project_id": project.id}).status_code == 403
    search = client.post(
        "/retrieval/search",
        json={"project_id": project.id, "query": "technical approach"},
    )
    assert search.status_code == 200, search.text
    assert search.json()["results"][0]["chunk_id"] == "chunk-alpha"
    assert "postgresql_retrieval_unavailable" in search.json()["degraded_reasons"]
    assert client.get("/export/deliverables/deliverable-alpha/docx").status_code == 403

    set_user(users["contributor"])
    denied_deliverable = client.post(
        "/deliverables",
        json={"project_id": project.id, "type": "proposal", "title": "Unauthorized"},
    )
    assert denied_deliverable.status_code == 403

    set_user(users["reviewer"])
    exported = client.get("/export/deliverables/deliverable-alpha/docx")
    assert exported.status_code == 200, exported.text

    set_user(users["outsider"])
    assert client.get("/deliverables", params={"project_id": project.id}).status_code == 404
    assert client.get(f"/documents/{resources['document'].id}/download").status_code == 404
    assert client.post(
        "/retrieval/search",
        json={"project_id": project.id, "query": "technical"},
    ).status_code == 404
