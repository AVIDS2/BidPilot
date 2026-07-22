import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.schemas import CurrentUser
from app.db import Base
from app.models import Organization, Project, ProjectMember, User
from app.access.service import require_project_capability


def _current(user: User) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        plan="starter",
        email_verified=True,
        disabled=False,
        org_id=user.org_id,
        org_slug="acme",
    )


@pytest.fixture()
def access_db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def project_users(access_db: Session):
    org = Organization(id="org-acme", slug="acme", name="Acme")
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
            password_hash="test-only",
            role="member",
            email_verified=True,
        )
        for role in ("owner", "manager", "contributor", "reviewer", "viewer", "outsider")
    }
    admin = User(
        id="user-admin",
        org_id=org.id,
        email="admin@acme.test",
        display_name="Administrator",
        password_hash="test-only",
        role="admin",
        email_verified=True,
    )
    access_db.add_all([org, project, *users.values(), admin])
    access_db.flush()
    access_db.add_all(
        [
            ProjectMember(project_id=project.id, user_id=users[role].id, role=role)
            for role in ("owner", "manager", "contributor", "reviewer", "viewer")
        ]
    )
    access_db.commit()
    return project, users, admin


@pytest.mark.parametrize(
    ("project_role", "capability", "allowed"),
    [
        ("owner", "project.members.manage", True),
        ("owner", "project.delete", True),
        ("manager", "project.manage", True),
        ("manager", "project.delete", False),
        ("manager", "requirements.assign", True),
        ("contributor", "requirements.write", True),
        ("contributor", "workflow.run", True),
        ("contributor", "requirements.assign", False),
        ("reviewer", "requirements.review", True),
        ("reviewer", "review.write", True),
        ("reviewer", "requirements.write", False),
        ("viewer", "project.read", True),
        ("viewer", "deliverables.export", False),
    ],
)
def test_project_capability_matrix(
    access_db: Session,
    project_users,
    project_role: str,
    capability: str,
    allowed: bool,
) -> None:
    project, users, _admin = project_users

    if allowed:
        access = require_project_capability(
            access_db,
            current_user=_current(users[project_role]),
            project_id=project.id,
            capability=capability,
        )
        assert access.project.id == project.id
        assert access.effective_role == project_role
    else:
        with pytest.raises(HTTPException) as exc_info:
            require_project_capability(
                access_db,
                current_user=_current(users[project_role]),
                project_id=project.id,
                capability=capability,
            )
        assert exc_info.value.status_code == 403


def test_non_member_cannot_discover_a_project(access_db: Session, project_users) -> None:
    project, users, _admin = project_users

    with pytest.raises(HTTPException) as exc_info:
        require_project_capability(
            access_db,
            current_user=_current(users["outsider"]),
            project_id=project.id,
            capability="project.read",
        )

    assert exc_info.value.status_code == 404


def test_organization_admin_has_audited_project_bypass(access_db: Session, project_users) -> None:
    project, _users, admin = project_users

    access = require_project_capability(
        access_db,
        current_user=_current(admin),
        project_id=project.id,
        capability="project.delete",
    )

    assert access.project.id == project.id
    assert access.effective_role == "admin"
    assert access.used_admin_bypass is True
