import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.schemas import CurrentUser
from app.auth.service import _hash_password
from app.db import Base, get_db
from app.main import app
from app.models import Organization, Project, Subscription, User
from app.usage.schemas import ProviderSource
from app.usage.service import record_usage_event


@pytest.fixture()
def sqlite_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as db:
        org = Organization(
            id="00000000-0000-0000-0000-000000000001",
            slug="default",
            name="Default Organization",
        )
        admin = User(
            id="dev-user",
            email="dev@docpilot.local",
            display_name="Dev User",
            password_hash=_hash_password("Test1234"),
            role="admin",
            email_verified=True,
            org_id=org.id,
        )
        db.add_all([org, admin])
        db.commit()
    return SessionLocal


@pytest.fixture()
def test_db(sqlite_session_factory):
    db = sqlite_session_factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(sqlite_session_factory):
    SessionLocal = sqlite_session_factory

    async def override_require_auth():
        return CurrentUser(
            id="dev-user",
            email="dev@docpilot.local",
            display_name="Dev User",
            role="admin",
            plan="professional",
            email_verified=True,
            disabled=False,
            org_id="00000000-0000-0000-0000-000000000001",
            org_slug="default",
        )

    def override_get_db():
        with SessionLocal() as db:
            yield db

    from app.auth.service import require_admin

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_admin] = override_require_auth
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _seed_billing_user(session, plan: str = "starter"):
    slug = f"billing-{plan}-{uuid.uuid4().hex[:8]}"
    org = Organization(slug=slug, name=f"Billing {plan}")
    session.add(org)
    session.flush()
    user = User(
        email=f"{plan}-{uuid.uuid4().hex[:8]}@example.com",
        display_name=plan,
        password_hash=_hash_password("Test1234"),
        role="admin",
        email_verified=True,
        org_id=org.id,
    )
    session.add(user)
    session.flush()
    session.add(Subscription(user_id=user.id, plan=plan, status="active"))
    project = Project(org_id=org.id, slug=f"{plan}-project-{uuid.uuid4().hex[:8]}", name="Project", scenario_package="bidpilot")
    session.add(project)
    session.commit()
    return user, project


def test_admin_can_read_billing_support(client, test_db):
    user, project = _seed_billing_user(test_db)
    record_usage_event(
        test_db,
        user_id=user.id,
        org_id=user.org_id,
        project_id=project.id,
        event_type="workflow_draft_started",
        provider_source=ProviderSource.OFFICIAL,
    )
    test_db.commit()

    resp = client.get(f"/ops/billing/users/{user.id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["plan"] == "starter"
    assert data["monthly_workflow_used"] == 1


def test_admin_can_read_billing_usage(client, test_db):
    user, project = _seed_billing_user(test_db)
    record_usage_event(
        test_db,
        user_id=user.id,
        org_id=user.org_id,
        project_id=project.id,
        event_type="workflow_draft_started",
        provider_source=ProviderSource.OFFICIAL,
    )
    test_db.commit()

    resp = client.get(f"/ops/billing/usage/{user.id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["provider_source"] == ProviderSource.OFFICIAL.value
