import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.schemas import CurrentUser
from app.auth.service import _hash_password
from app.db import Base, get_db
from app.main import app
from app.models import Organization, Project, User


def _make_org_user_and_project(db: Session, slug: str):
    org = Organization(slug=slug, name=slug)
    db.add(org)
    db.flush()
    user = User(
        email=f"{slug}-{uuid.uuid4().hex[:8]}@example.com",
        display_name=slug,
        password_hash=_hash_password("Test1234"),
        role="member",
        email_verified=True,
        org_id=org.id,
    )
    db.add(user)
    project = Project(
        org_id=org.id,
        slug=f"{slug}-{uuid.uuid4().hex[:8]}",
        name=f"{slug} project",
        scenario_package="bidpilot",
    )
    db.add(project)
    db.commit()
    db.refresh(user)
    db.refresh(project)
    return org, user, project


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as session:
        default_org = Organization(
            id="00000000-0000-0000-0000-000000000001",
            slug="default",
            name="Default Organization",
        )
        session.add(default_org)
        session.commit()
        yield SessionLocal


def _override_user(user):
    async def dependency():
        return CurrentUser(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            plan="starter",
            email_verified=True,
            disabled=False,
            org_id=user.org_id,
            org_slug="",
        )

    return dependency


def test_get_project_rejects_cross_org_access(db_session, client):
    SessionLocal = db_session
    with SessionLocal() as seed_db:
        (_, user_a, _project_a) = _make_org_user_and_project(seed_db, "org-a")
        (_, _user_b, project_b) = _make_org_user_and_project(seed_db, "org-b")
    from app.auth.service import require_auth

    def override_get_db():
        with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_auth] = _override_user(user_a)
    try:
        response = client.get(f"/projects/{project_b.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_update_and_delete_project_reject_cross_org_access(db_session, client):
    SessionLocal = db_session
    with SessionLocal() as seed_db:
        (_, user_a, _project_a) = _make_org_user_and_project(seed_db, "org-a")
        (_, _user_b, project_b) = _make_org_user_and_project(seed_db, "org-b")
    from app.auth.service import require_auth

    def override_get_db():
        with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_auth] = _override_user(user_a)
    try:
        patch_response = client.patch(f"/projects/{project_b.id}", json={"status": "archived"})
        delete_response = client.delete(f"/projects/{project_b.id}")
    finally:
        app.dependency_overrides.clear()

    assert patch_response.status_code == 404
    assert delete_response.status_code == 404
