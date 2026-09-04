import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.schemas import CurrentUser
from app.auth.service import _hash_password, require_auth
from app.db import Base, get_db
from app.main import app
from app.models import ChatConversation, Organization, Project, ProjectMember, User


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
def conversation_db() -> tuple[Session, dict[str, User], Project, ChatConversation]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        org = Organization(id="org-acme", slug="acme", name="Acme")
        project = Project(
            id="project-alpha",
            org_id=org.id,
            slug="alpha",
            name="Restricted Bid",
            scenario_package="bidpilot",
        )
        users = {
            name: User(
                id=f"user-{name}",
                org_id=org.id,
                email=f"{name}@acme.test",
                display_name=name.title(),
                password_hash=_hash_password("Test1234"),
                role="member",
                email_verified=True,
            )
            for name in ("owner", "non_member")
        }
        conversation = ChatConversation(
            id="conversation-alpha",
            user_id=users["owner"].id,
            project_id=project.id,
        )
        session.add_all([org, project, *users.values(), conversation])
        session.flush()
        session.add(ProjectMember(project_id=project.id, user_id=users["owner"].id, role="owner"))
        session.commit()
        yield session, users, project, conversation
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_conversation_context_requires_project_membership(conversation_db) -> None:
    from app.chat.service import resolve_conversation_project_context

    db, users, project, conversation = conversation_db

    assert resolve_conversation_project_context(
        db,
        _current(users["owner"]),
        conversation_id=conversation.id,
        requested_project_id=project.id,
    ) == project.id

    with pytest.raises(HTTPException) as access_error:
        resolve_conversation_project_context(
            db,
            _current(users["non_member"]),
            conversation_id=None,
            requested_project_id=project.id,
        )
    assert access_error.value.status_code == 404

    with pytest.raises(HTTPException) as mismatch_error:
        resolve_conversation_project_context(
            db,
            _current(users["owner"]),
            conversation_id=conversation.id,
            requested_project_id="different-project",
        )
    assert mismatch_error.value.status_code == 409


def test_deleted_project_conversation_is_recoverable_as_unbound_history(conversation_db) -> None:
    from app.chat.service import resolve_conversation_project_context

    db, users, project, conversation = conversation_db
    project.status = "deleted"
    db.commit()

    assert resolve_conversation_project_context(
        db,
        _current(users["owner"]),
        conversation_id=conversation.id,
        requested_project_id=project.id,
    ) is None

    db.refresh(conversation)
    assert conversation.project_id is None


def test_chat_and_assistant_reject_inaccessible_project_context(conversation_db, monkeypatch) -> None:
    _db, users, project, _conversation = conversation_db
    engine = _db.bind
    assert engine is not None
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    active_user = {"value": users["non_member"]}

    async def override_require_auth() -> CurrentUser:
        return _current(active_user["value"])

    def override_get_db():
        with SessionLocal() as db:
            yield db

    async def fake_stream(*_args, **_kwargs):
        yield "event: end\ndata: {}\n\n"

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_auth] = override_require_auth
    monkeypatch.setattr("app.chat.router.stream_chat_response", fake_stream)
    try:
        client = TestClient(app)
        chat = client.post(
            "/chat/stream",
            json={"message": "Summarize this project", "project_id": project.id},
        )
        assistant = client.post(
            "/assistant/stream",
            json={"message": "Summarize this project", "project_id": project.id},
        )
        conversations = client.get("/chat/conversations", params={"project_id": project.id})
    finally:
        app.dependency_overrides.clear()

    assert chat.status_code == 404
    assert assistant.status_code == 404
    assert conversations.status_code == 404
