import uuid
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.schemas import CurrentUser
from app.auth.service import _hash_password
from app.db import Base, get_db
from app.main import app
from app.models import Organization, Project, Subscription, User, UsageEvent
from app.usage.schemas import ProviderSource
from app.usage.service import record_usage_event


def _make_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as session:
        session.add(
            Organization(
                id="00000000-0000-0000-0000-000000000001",
                slug="default",
                name="Default Organization",
            )
        )
        session.commit()
    return SessionLocal


def _make_user_project(SessionLocal, plan: str = "starter"):
    db = SessionLocal()
    org = Organization(slug=f"quota-{uuid.uuid4().hex[:8]}", name="Quota Org")
    db.add(org)
    db.flush()
    user = User(
        email=f"quota-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Quota User",
        password_hash=_hash_password("Test1234"),
        role="member",
        email_verified=True,
        org_id=org.id,
    )
    db.add(user)
    db.flush()
    db.add(Subscription(user_id=user.id, plan=plan, status="active"))
    project = Project(
        org_id=org.id,
        slug=f"quota-project-{uuid.uuid4().hex[:8]}",
        name="Quota Project",
        scenario_package="bidpilot",
    )
    db.add(project)
    db.commit()
    db.refresh(user)
    db.refresh(project)
    return db, user, project


def _override_user(user):
    async def dependency():
        return CurrentUser(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            plan="starter",
            org_id=user.org_id,
            org_slug="",
            email_verified=True,
            disabled=False,
        )

    return dependency


def _override_get_db(sessionmaker_):
    def dependency():
        with sessionmaker_() as session:
            yield session

    return dependency


def test_draft_section_blocks_starter_fourth_official_run(client):
    SessionLocal = _make_db()
    db, user, project = _make_user_project(SessionLocal, "starter")
    try:
        for _ in range(3):
            record_usage_event(
                db,
                user_id=user.id,
                org_id=user.org_id,
                project_id=project.id,
                event_type="workflow_draft_started",
                provider_source=ProviderSource.OFFICIAL,
            )
        db.commit()

        from app import db as app_db
        from app.auth.service import require_auth

        app.dependency_overrides[get_db] = _override_get_db(SessionLocal)
        app.dependency_overrides[require_auth] = _override_user(user)
        response = client.post(
            "/drafting/sections",
            json={"project_id": project.id, "section_key": "technical-approach"},
        )
    finally:
        app.dependency_overrides.clear()
        db.close()

    assert response.status_code == 403
    assert "starter workflow trial limit" in response.text


def test_draft_section_records_usage_before_enqueue(client):
    SessionLocal = _make_db()
    db, user, project = _make_user_project(SessionLocal, "starter")
    try:
        from app.auth.service import require_auth

        app.dependency_overrides[get_db] = _override_get_db(SessionLocal)
        app.dependency_overrides[require_auth] = _override_user(user)
        with patch("app.celery_client.celery.send_task") as mock_send_task:
            response = client.post(
                "/drafting/sections",
                json={"project_id": project.id, "section_key": "technical-approach"},
            )
            assert response.status_code == 202
            assert mock_send_task.called

        events = db.query(UsageEvent).filter_by(user_id=user.id, event_type="workflow_draft_started").all()
        assert len(events) == 1
        assert events[0].provider_source == "official"
    finally:
        app.dependency_overrides.clear()
        db.close()
