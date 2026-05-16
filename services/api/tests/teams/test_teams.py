"""Test Team CRUD APIs."""
import uuid

from app.models import Team, TeamMember, User
from app.auth.service import register_user_command, login_command, _get_or_create_default_org
from app.auth.schemas import UserRegister


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _setup_admin(test_db, role: str = "admin"):
    """Create a verified user with the given role, return (token, org)."""
    suffix = _uid()
    email = f"{role}-{suffix}@docpilot.ai"
    org = _get_or_create_default_org(test_db)
    register_user_command(test_db, UserRegister(email=email, display_name=f"{role} User", password="Test1234"))
    u = test_db.query(User).filter_by(email=email).first()
    u.role = role
    u.email_verified = True
    test_db.commit()
    token = login_command(test_db, email, "Test1234").access_token
    return token, org, suffix, email


def test_create_team(test_db, client):
    """Admin should be able to create a team in their org."""
    token, org, suffix, _ = _setup_admin(test_db, "admin")
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
    token, org, suffix, _ = _setup_admin(test_db, "admin")
    t = Team(id=f"t-{suffix}", org_id=org.id, name="Design", slug=f"design-{suffix}")
    test_db.add(t)
    test_db.commit()

    resp = client.get("/teams", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


def test_add_and_remove_member(test_db, client):
    """Admin should be able to add and remove team members."""
    token, org, suffix, _ = _setup_admin(test_db, "admin")

    # Create member user
    member_email = f"member-{suffix}@docpilot.ai"
    register_user_command(test_db, UserRegister(email=member_email, display_name="Member", password="Test1234"))
    member = test_db.query(User).filter_by(email=member_email).first()
    member.email_verified = True
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


def test_non_admin_cannot_create_team(test_db, client):
    """Non-admin should receive 403 when trying to create a team."""
    token, org, suffix, _ = _setup_admin(test_db, "member")

    resp = client.post(
        "/teams",
        json={"name": "Bad Team", "slug": "bad"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_update_team(test_db, client):
    """Admin should be able to rename a team."""
    token, org, suffix, _ = _setup_admin(test_db, "admin")

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
    token, org, suffix, _ = _setup_admin(test_db, "admin")

    team = Team(id=f"tdeld-{suffix}", org_id=org.id, name="To Delete", slug=f"del-{suffix}")
    test_db.add(team)
    test_db.commit()

    resp = client.delete(
        f"/teams/{team.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204
