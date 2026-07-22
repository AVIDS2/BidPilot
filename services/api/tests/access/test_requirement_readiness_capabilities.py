
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.schemas import CurrentUser
from app.auth.service import _hash_password, get_current_user, require_auth
from app.db import Base, get_db
from app.main import app
from app.models import (
    Organization,
    OrganizationMembership,
    Project,
    ProjectMember,
    RequirementItem,
    User,
)


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
def requirement_client():
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
            for role in ("owner", "manager", "contributor", "reviewer", "viewer")
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
        users["unassigned"] = User(
            id="user-unassigned",
            org_id=org.id,
            email="unassigned@acme.test",
            display_name="Unassigned",
            password_hash=_hash_password("Test1234"),
            role="member",
            email_verified=True,
        )
        users["admin"] = User(
            id="user-admin",
            org_id=org.id,
            email="admin@acme.test",
            display_name="Administrator",
            password_hash=_hash_password("Test1234"),
            role="admin",
            email_verified=True,
        )
        requirement = RequirementItem(
            id="requirement-alpha",
            project_id=project.id,
            section_key="security",
            requirement_text="The response must document access controls.",
        )
        db.add_all([org, outsider_org, project, *users.values(), requirement])
        db.flush()
        db.add_all(
            [
                OrganizationMembership(
                    org_id=org.id,
                    user_id=users[role].id,
                    role="owner" if role == "owner" else "member",
                )
                for role in (
                    "owner",
                    "manager",
                    "contributor",
                    "reviewer",
                    "viewer",
                    "unassigned",
                    "admin",
                )
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
                for role in ("owner", "manager", "contributor", "reviewer", "viewer")
            ]
        )
        db.commit()

    active_user = {"value": users["owner"]}

    async def override_current_user() -> CurrentUser:
        return _current(active_user["value"])

    def override_get_db():
        with SessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_auth] = override_current_user
    app.dependency_overrides[get_current_user] = override_current_user
    try:
        yield TestClient(app), users, project, lambda user: active_user.update(value=user)
    finally:
        app.dependency_overrides.clear()


def test_requirement_writes_assignments_and_reviews_follow_project_capabilities(requirement_client) -> None:
    client, users, project, set_user = requirement_client

    set_user(users["contributor"])
    updated = client.patch(
        "/requirements/requirement-alpha",
        json={"lock_version": 1, "priority": "high"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["lock_version"] == 2

    denied_assignment = client.post(
        "/requirements/bulk-assign",
        json={
            "requirement_ids": ["requirement-alpha"],
            "lock_versions": {"requirement-alpha": 2},
            "owner_user_id": users["owner"].id,
        },
    )
    assert denied_assignment.status_code == 403

    denied_review = client.patch(
        "/requirements/requirement-alpha",
        json={"lock_version": 2, "verification_status": "verified"},
    )
    assert denied_review.status_code == 403

    set_user(users["reviewer"])
    reviewed = client.patch(
        "/requirements/requirement-alpha",
        json={"lock_version": 2, "verification_status": "verified"},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["verification_status"] == "verified"

    set_user(users["viewer"])
    visible = client.get("/requirements", params={"project_id": project.id})
    assert visible.status_code == 200, visible.text
    assert [item["id"] for item in visible.json()] == ["requirement-alpha"]

    denied_create = client.post(
        "/requirements",
        json={
            "project_id": project.id,
            "section_key": "scope",
            "requirement_text": "Viewer must not create requirements.",
        },
    )
    assert denied_create.status_code == 403

    set_user(users["outsider"])
    hidden = client.get("/requirements", params={"project_id": project.id})
    assert hidden.status_code == 404


def test_readiness_uses_read_and_export_capabilities(requirement_client, monkeypatch) -> None:
    client, users, project, set_user = requirement_client
    uploads: dict[str, bytes] = {}

    def fake_upload(project_id: str, object_name: str, data: bytes, _content_type: str) -> str:
        assert project_id == project.id
        uploads[object_name] = data
        return f"bucket/{object_name}"

    def fake_download(project_id: str, object_name: str) -> bytes:
        assert project_id == project.id
        return uploads[object_name]

    monkeypatch.setattr("app.readiness.service.upload_bytes", fake_upload)
    monkeypatch.setattr("app.readiness.service.download_bytes", fake_download)

    set_user(users["viewer"])
    summary = client.get(f"/readiness/projects/{project.id}")
    assert summary.status_code == 200, summary.text

    set_user(users["contributor"])
    denied_export = client.post(f"/readiness/projects/{project.id}/packs")
    assert denied_export.status_code == 403

    set_user(users["reviewer"])
    generated = client.post(f"/readiness/projects/{project.id}/packs")
    assert generated.status_code == 201, generated.text

    set_user(users["viewer"])
    downloaded = client.get(f"/readiness/packs/{generated.json()['id']}/xlsx")
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content.startswith(b"PK")

    set_user(users["outsider"])
    hidden = client.get(f"/readiness/projects/{project.id}")
    assert hidden.status_code == 404


def test_requirement_assignment_targets_must_be_eligible_project_members(requirement_client) -> None:
    client, users, _project, set_user = requirement_client
    set_user(users["owner"])

    non_member = client.patch(
        "/requirements/requirement-alpha",
        json={"lock_version": 1, "owner_user_id": users["unassigned"].id},
    )
    assert non_member.status_code == 400
    assert non_member.json()["detail"] == "Owner is not a project member"

    wrong_project_role = client.patch(
        "/requirements/requirement-alpha",
        json={"lock_version": 1, "owner_user_id": users["reviewer"].id},
    )
    assert wrong_project_role.status_code == 400
    assert wrong_project_role.json()["detail"] == "Owner does not have the required project capability"

    assigned = client.patch(
        "/requirements/requirement-alpha",
        json={"lock_version": 1, "owner_user_id": users["contributor"].id},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["owner_user_id"] == users["contributor"].id

    admin_assignment = client.patch(
        "/requirements/requirement-alpha",
        json={"lock_version": assigned.json()["lock_version"], "reviewer_user_id": users["admin"].id},
    )
    assert admin_assignment.status_code == 200, admin_assignment.text
    assert admin_assignment.json()["reviewer_user_id"] == users["admin"].id
