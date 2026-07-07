import uuid
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.schemas import CurrentUser
from app.auth.service import _hash_password, require_auth
from app.db import Base, get_db
from app.main import app
from app.models import Organization, Project, Subscription, User
from app.usage.schemas import ProviderSource
from app.usage.service import EMBEDDING_INDEX_STARTED, record_usage_event


def _make_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return SessionLocal


def _make_user_project(SessionLocal, plan: str = "starter") -> tuple[User, Project]:
    db = SessionLocal()
    try:
        org = Organization(slug=f"bundle-usage-{uuid.uuid4().hex[:8]}", name="Bundle Usage")
        db.add(org)
        db.flush()
        user = User(
            email=f"bundle-usage-{uuid.uuid4().hex[:8]}@example.com",
            display_name="Bundle Usage",
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
            slug=f"bundle-usage-project-{uuid.uuid4().hex[:8]}",
            name="Bundle Usage Project",
            scenario_package="bidpilot",
        )
        db.add(project)
        db.commit()
        db.refresh(user)
        db.refresh(project)
        return user, project
    finally:
        db.close()


def _override_user(user: User):
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


def _override_get_db(SessionLocal):
    def dependency():
        with SessionLocal() as session:
            yield session

    return dependency


def test_register_bundle_blocks_starter_after_indexing_limit(client):
    SessionLocal = _make_db()
    user, project = _make_user_project(SessionLocal)
    with SessionLocal() as db:
        for _ in range(5):
            record_usage_event(
                db,
                user_id=user.id,
                org_id=user.org_id,
                project_id=project.id,
                event_type=EMBEDDING_INDEX_STARTED,
                provider_source=ProviderSource.OFFICIAL,
            )
        db.commit()

    try:
        app.dependency_overrides[get_db] = _override_get_db(SessionLocal)
        app.dependency_overrides[require_auth] = _override_user(user)
        with patch("app.celery_client.celery.send_task"):
            response = client.post(
                "/bundles",
                json={"project_id": project.id, "label": "RFP Pack", "source_type": "upload"},
            )

        assert response.status_code == 403
        assert "starter indexing limit" in response.text
    finally:
        app.dependency_overrides.clear()
