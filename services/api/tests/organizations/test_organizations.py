"""Test Organization management APIs."""
import uuid

from app.models import Organization, User
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
    u.email_verified = True
    test_db.commit()
    token = login_command(test_db, email, "Test1234").access_token

    orig_org_id = u.org_id

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
    test_db.add(org2)
    test_db.commit()

    resp = client.post(
        "/organizations/switch",
        json={"org_id": org2.id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["org_id"] == org2.id


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
