import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.schemas import CurrentUser
from app.auth.service import _hash_password, require_auth
from app.db import Base, get_db
from app.main import app
from app.models import Organization, OrganizationMembership, User


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
def project_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as db:
        org = Organization(id="org-acme", slug="acme", name="Acme")
        other_org = Organization(id="org-other", slug="other", name="Other")
        users = {
            "owner": User(
                id="user-owner",
                org_id=org.id,
                email="owner@acme.test",
                display_name="Owner",
                password_hash=_hash_password("Test1234"),
                role="member",
                email_verified=True,
            ),
            "contributor": User(
                id="user-contributor",
                org_id=org.id,
                email="contributor@acme.test",
                display_name="Contributor",
                password_hash=_hash_password("Test1234"),
                role="member",
                email_verified=True,
            ),
            "admin": User(
                id="user-admin",
                org_id=org.id,
                email="admin@acme.test",
                display_name="Admin",
                password_hash=_hash_password("Test1234"),
                role="admin",
                email_verified=True,
            ),
            "outsider": User(
                id="user-outsider",
                org_id=other_org.id,
                email="outsider@other.test",
                display_name="Outsider",
                password_hash=_hash_password("Test1234"),
                role="member",
                email_verified=True,
            ),
        }
        memberships = [
            OrganizationMembership(org_id=org.id, user_id=users["owner"].id, role="owner"),
            OrganizationMembership(org_id=org.id, user_id=users["contributor"].id, role="member"),
            OrganizationMembership(org_id=org.id, user_id=users["admin"].id, role="admin"),
            OrganizationMembership(org_id=other_org.id, user_id=users["outsider"].id, role="member"),
        ]
        db.add_all([org, other_org, *users.values(), *memberships])
        db.commit()

    active_user = {"value": users["owner"]}

    async def override_require_auth():
        return _current(active_user["value"])

    def override_get_db():
        with SessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_auth] = override_require_auth
    try:
        yield TestClient(app), SessionLocal, users, lambda user: active_user.update(value=user)
    finally:
        app.dependency_overrides.clear()


def test_project_creation_creates_an_owner_membership(project_client) -> None:
    client, _SessionLocal, users, _set_user = project_client

    created = client.post(
        "/projects",
        json={"name": "Restricted Bid", "scenario_package": "bidpilot"},
    )
    assert created.status_code == 201, created.text

    members = client.get(f"/projects/{created.json()['id']}/members")
    assert members.status_code == 200, members.text
    assert members.json() == [
        {
            "user_id": users["owner"].id,
            "display_name": "Owner",
            "role": "owner",
            "source": "membership",
        }
    ]


def test_owner_can_add_member_and_non_member_cannot_discover_project(project_client) -> None:
    client, _SessionLocal, users, set_user = project_client
    project = client.post(
        "/projects",
        json={"name": "Private Bid", "scenario_package": "bidpilot"},
    ).json()

    added = client.post(
        f"/projects/{project['id']}/members",
        json={"user_id": users["contributor"].id, "role": "contributor"},
    )
    assert added.status_code == 201, added.text
    assert added.json()["role"] == "contributor"

    set_user(users["contributor"])
    assert client.get(f"/projects/{project['id']}").status_code == 200
    assert client.patch(f"/projects/{project['id']}", json={"status": "archived"}).status_code == 403

    set_user(users["outsider"])
    assert client.get(f"/projects/{project['id']}").status_code == 404
    assert client.get("/projects").json() == []


def test_owner_can_add_member_who_is_currently_active_in_another_org(project_client) -> None:
    client, SessionLocal, users, _set_user = project_client
    project = client.post(
        "/projects",
        json={"name": "Shared Bid", "scenario_package": "bidpilot"},
    ).json()

    with SessionLocal() as db:
        contributor = db.get(User, users["contributor"].id)
        contributor.org_id = "org-other"
        db.add(
            OrganizationMembership(
                org_id="org-other",
                user_id=contributor.id,
                role="member",
            )
        )
        db.commit()

    added = client.post(
        f"/projects/{project['id']}/members",
        json={"user_id": users["contributor"].id, "role": "contributor"},
    )

    assert added.status_code == 201, added.text


def test_only_owner_or_org_admin_can_manage_project_members(project_client) -> None:
    client, _SessionLocal, users, set_user = project_client
    project = client.post(
        "/projects",
        json={"name": "Managed Bid", "scenario_package": "bidpilot"},
    ).json()
    client.post(
        f"/projects/{project['id']}/members",
        json={"user_id": users["contributor"].id, "role": "contributor"},
    )

    set_user(users["contributor"])
    denied = client.post(
        f"/projects/{project['id']}/members",
        json={"user_id": users["admin"].id, "role": "reviewer"},
    )
    assert denied.status_code == 403

    set_user(users["admin"])
    changed = client.patch(
        f"/projects/{project['id']}/members/{users['contributor'].id}",
        json={"role": "reviewer"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["role"] == "reviewer"
