"""Test Team CRUD APIs."""
import uuid

from app.models import Organization, OrganizationMembership, Team, User
from app.auth.service import login_command, register_user_command
from app.auth.schemas import UserRegister
from app.entitlements.service import upsert_organization_subscription_command
from app.organizations.service import create_organization_membership_command


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _setup_workspace_user(test_db, role: str = "owner"):
    """Create a verified user with a workspace role, return (token, org)."""
    suffix = _uid()
    email = f"{role}-{suffix}@docpilot.ai"
    register_user_command(test_db, UserRegister(email=email, display_name=f"{role} User", password="Test1234"))
    u = test_db.query(User).filter_by(email=email).first()
    u.email_verified = True
    membership = test_db.query(OrganizationMembership).filter_by(org_id=u.org_id, user_id=u.id).one()
    membership.role = role
    test_db.commit()
    org = test_db.get(Organization, u.org_id)
    assert org is not None
    token = login_command(test_db, email, "Test1234").access_token
    return token, org, suffix, email


def test_create_team(test_db, client):
    """Admin should be able to create a team in their org."""
    token, org, suffix, _ = _setup_workspace_user(test_db, "owner")
    resp = client.post(
        "/teams",
        json={"name": "Engineering", "slug": f"eng-{suffix}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Engineering"
    assert data["org_id"] == org.id


def test_list_teams(test_db, client):
    """Should list teams scoped to the user's org."""
    token, org, suffix, _ = _setup_workspace_user(test_db, "owner")
    t = Team(id=f"t-{suffix}", org_id=org.id, name="Design", slug=f"design-{suffix}")
    test_db.add(t)
    test_db.commit()

    resp = client.get("/teams", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


def test_add_and_remove_member(test_db, client):
    """A workspace owner should be able to add and remove team members."""
    token, org, suffix, owner_email = _setup_workspace_user(test_db, "owner")

    # Create member user
    member_email = f"member-{suffix}@docpilot.ai"
    register_user_command(test_db, UserRegister(email=member_email, display_name="Member", password="Test1234"))
    member = test_db.query(User).filter_by(email=member_email).first()
    member.email_verified = True
    owner = test_db.query(User).filter_by(email=owner_email).first()
    assert owner is not None
    upsert_organization_subscription_command(
        test_db,
        org_id=org.id,
        billing_owner_user_id=owner.id,
        plan="professional",
        seat_limit=2,
    )
    create_organization_membership_command(
        test_db,
        org_id=org.id,
        user_id=member.id,
        role="member",
    )
    test_db.commit()

    # Create team
    team = Team(id=f"tmem-{suffix}", org_id=org.id, name="QA", slug=f"qa-{suffix}")
    test_db.add(team)
    test_db.commit()

    # Add member
    resp = client.post(
        f"/teams/{team.id}/members",
        json={"user_id": member.id, "role": "member"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["user_id"] == member.id

    # Remove member
    resp = client.delete(
        f"/teams/{team.id}/members/{member.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204


def test_team_rejects_user_without_active_organization_membership(test_db, client):
    token, org, suffix, _ = _setup_workspace_user(test_db, "owner")
    outsider_org = Organization(
        id=f"outsider-org-{suffix}",
        slug=f"outsider-org-{suffix}",
        name="Outsider Org",
    )
    outsider = User(
        id=f"outsider-{suffix}",
        org_id=outsider_org.id,
        email=f"outsider-{suffix}@docpilot.ai",
        display_name="Outsider",
        password_hash="test-only",
        email_verified=True,
    )
    team = Team(id=f"reject-{suffix}", org_id=org.id, name="Reject", slug=f"reject-{suffix}")
    test_db.add_all([outsider_org, outsider, team])
    test_db.commit()

    response = client.post(
        f"/teams/{team.id}/members",
        json={"user_id": outsider.id, "role": "member"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "active organization member" in response.json()["detail"]


def test_workspace_member_cannot_create_team(test_db, client):
    """A workspace member should receive 403 when trying to create a team."""
    token, org, suffix, _ = _setup_workspace_user(test_db, "member")

    resp = client.post(
        "/teams",
        json={"name": "Bad Team", "slug": "bad"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_update_team(test_db, client):
    """Admin should be able to rename a team."""
    token, org, suffix, _ = _setup_workspace_user(test_db, "owner")

    team = Team(id=f"tupd-{suffix}", org_id=org.id, name="Old Name", slug=f"old-{suffix}")
    test_db.add(team)
    test_db.commit()

    resp = client.patch(
        f"/teams/{team.id}",
        json={"name": "New Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


def test_delete_team(test_db, client):
    """Admin should be able to delete a team."""
    token, org, suffix, _ = _setup_workspace_user(test_db, "owner")

    team = Team(id=f"tdeld-{suffix}", org_id=org.id, name="To Delete", slug=f"del-{suffix}")
    test_db.add(team)
    test_db.commit()

    resp = client.delete(
        f"/teams/{team.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204
