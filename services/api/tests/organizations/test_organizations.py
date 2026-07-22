"""Test Organization management APIs."""
import uuid

from app.models import Organization, OrganizationMembership, User
from app.auth.service import register_user_command, login_command
from app.auth.schemas import UserRegister


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def test_create_org_and_switch(test_db, client):
    """User creates a new org and gets switched to it."""
    suffix = _uid()
    email = f"org-creator-{suffix}@docpilot.ai"
    register_user_command(test_db, UserRegister(email=email, display_name="Org Creator", password="Test1234"))
    u = test_db.query(User).filter_by(email=email).first()
    initial_org_id = u.org_id
    u.email_verified = True
    test_db.commit()
    token = login_command(test_db, email, "Test1234").access_token

    resp = client.post(
        "/organizations",
        json={"name": f"My Org {suffix}", "slug": f"my-org-{suffix}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == f"My Org {suffix}"
    assert data["slug"] == f"my-org-{suffix}"
    new_org_id = data["id"]

    # User should have been switched to the new org
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["org_id"] == new_org_id
    orgs = client.get("/organizations", headers={"Authorization": f"Bearer {token}"}).json()
    assert {org["id"] for org in orgs} >= {initial_org_id, new_org_id}


def test_switch_org(test_db, client):
    """User should be able to switch between orgs."""
    suffix = _uid()
    email = f"switcher-{suffix}@docpilot.ai"
    register_user_command(test_db, UserRegister(email=email, display_name="Switcher", password="Test1234"))
    u = test_db.query(User).filter_by(email=email).first()
    u.email_verified = True
    test_db.commit()
    token = login_command(test_db, email, "Test1234").access_token

    # Create a second org
    org2 = Organization(id=f"o2-{suffix}", slug=f"sw-org2-{suffix}", name="Switch Org 2")
    test_db.add_all(
        [
            org2,
            OrganizationMembership(org_id=org2.id, user_id=u.id, role="member"),
        ]
    )
    test_db.commit()

    resp = client.post(
        "/organizations/switch",
        json={"org_id": org2.id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["org_id"] == org2.id


def test_switch_org_rejects_nonmember_without_mutating_active_context(test_db, client):
    suffix = _uid()
    email = f"nonmember-{suffix}@docpilot.ai"
    register_user_command(test_db, UserRegister(email=email, display_name="Nonmember", password="Test1234"))
    user = test_db.query(User).filter_by(email=email).first()
    user.email_verified = True
    original_org_id = user.org_id
    target = Organization(id=f"blocked-{suffix}", slug=f"blocked-{suffix}", name="Blocked Org")
    test_db.add(target)
    test_db.commit()
    token = login_command(test_db, email, "Test1234").access_token

    response = client.post(
        "/organizations/switch",
        json={"org_id": target.id},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    test_db.refresh(user)
    assert user.org_id == original_org_id


def test_list_user_orgs(test_db, client):
    """Should list orgs that the user belongs to."""
    suffix = _uid()
    email = f"lister-{suffix}@docpilot.ai"
    register_user_command(test_db, UserRegister(email=email, display_name="Lister", password="Test1234"))
    u = test_db.query(User).filter_by(email=email).first()
    u.email_verified = True
    test_db.commit()
    token = login_command(test_db, email, "Test1234").access_token

    resp = client.get("/organizations", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    orgs = resp.json()
    assert len(orgs) >= 1


def test_list_current_org_members_excludes_other_tenants(test_db, client):
    suffix = _uid()
    email = f"member-lister-{suffix}@docpilot.ai"
    register_user_command(test_db, UserRegister(email=email, display_name="Member Lister", password="Test1234"))
    user = test_db.query(User).filter_by(email=email).first()
    user.email_verified = True

    colleague = User(
        id=str(uuid.uuid4()),
        org_id=user.org_id,
        email=f"colleague-{suffix}@docpilot.ai",
        display_name="Bid Reviewer",
        role="member",
        password_hash="test-only",
        email_verified=True,
    )
    other_org = Organization(id=str(uuid.uuid4()), slug=f"other-members-{suffix}", name="Other Members Org")
    outsider = User(
        id=str(uuid.uuid4()),
        org_id=other_org.id,
        email=f"outsider-{suffix}@docpilot.ai",
        display_name="Outsider",
        role="admin",
        password_hash="test-only",
        email_verified=True,
    )
    colleague_membership = OrganizationMembership(
        org_id=user.org_id,
        user_id=colleague.id,
        role="member",
    )
    test_db.add_all([colleague, colleague_membership, other_org, outsider])
    test_db.commit()
    token = login_command(test_db, email, "Test1234").access_token

    response = client.get(
        "/organizations/current/members",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    members = response.json()
    member_ids = {member["id"] for member in members}
    assert {user.id, colleague.id}.issubset(member_ids)
    assert outsider.id not in member_ids
    assert {"Member Lister", "Bid Reviewer"}.issubset(
        {member["display_name"] for member in members}
    )
    assert all(
        set(member) == {"id", "display_name", "email", "role", "is_billing_owner"}
        for member in members
    )


def test_create_org_duplicate_slug(test_db, client):
    """Creating an org with duplicate slug should fail."""
    suffix = _uid()
    email = f"dup-{suffix}@docpilot.ai"
    register_user_command(test_db, UserRegister(email=email, display_name="Dup", password="Test1234"))
    u = test_db.query(User).filter_by(email=email).first()
    u.email_verified = True
    test_db.commit()
    token = login_command(test_db, email, "Test1234").access_token

    slug = f"dup-slug-{suffix}"
    resp = client.post(
        "/organizations",
        json={"name": "First", "slug": slug},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201

    # Create a second user and try the same slug
    email2 = f"dup2-{suffix}@docpilot.ai"
    register_user_command(test_db, UserRegister(email=email2, display_name="Dup2", password="Test1234"))
    u2 = test_db.query(User).filter_by(email=email2).first()
    u2.email_verified = True
    test_db.commit()
    token2 = login_command(test_db, email2, "Test1234").access_token

    resp = client.post(
        "/organizations",
        json={"name": "Second", "slug": slug},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 400


def test_switch_to_nonexistent_org(test_db, client):
    """Switching to a non-existent org should fail."""
    suffix = _uid()
    email = f"badsw-{suffix}@docpilot.ai"
    register_user_command(test_db, UserRegister(email=email, display_name="Bad Switcher", password="Test1234"))
    u = test_db.query(User).filter_by(email=email).first()
    u.email_verified = True
    test_db.commit()
    token = login_command(test_db, email, "Test1234").access_token

    resp = client.post(
        "/organizations/switch",
        json={"org_id": "nonexistent-org-id"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
