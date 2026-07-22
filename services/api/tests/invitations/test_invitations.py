"""Test invitation flow — invite, accept, register."""
import uuid

from app.models import (
    Invitation,
    Organization,
    OrganizationMembership,
    OrganizationSubscription,
    User,
)
from app.auth.service import register_user_command
from app.auth.schemas import UserRegister
from app.invitations.service import accept_invitation_command, create_invitation_command


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def test_create_invitation(test_db, client):
    """Admin should be able to create an invitation."""
    suffix = _uid()
    email = f"inv-admin-{suffix}@docpilot.ai"
    from app.auth.service import _get_or_create_default_org
    from app.auth.service import login_command
    _get_or_create_default_org(test_db)
    register_user_command(test_db, UserRegister(email=email, display_name="Inv Admin", password="Test1234"))
    u = test_db.query(User).filter_by(email=email).first()
    u.role = "admin"
    u.email_verified = True
    test_db.query(OrganizationMembership).filter_by(
        org_id=u.org_id,
        user_id=u.id,
    ).one().role = "admin"
    test_db.commit()
    token = login_command(test_db, email, "Test1234").access_token

    invite_email = f"invitee-{suffix}@docpilot.ai"
    resp = client.post(
        "/invitations",
        json={"email": invite_email},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == invite_email
    assert resp.json()["status"] == "pending"


def test_workspace_member_cannot_create_invitation(test_db, client):
    suffix = _uid()
    email = f"inv-member-{suffix}@docpilot.ai"
    from app.auth.service import _get_or_create_default_org, login_command

    _get_or_create_default_org(test_db)
    register_user_command(
        test_db,
        UserRegister(email=email, display_name="Invitation Member", password="Test1234"),
    )
    user = test_db.query(User).filter_by(email=email).one()
    user.email_verified = True
    user.role = "admin"  # Global role must not bypass workspace membership authority.
    test_db.query(OrganizationMembership).filter_by(
        org_id=user.org_id,
        user_id=user.id,
    ).one().role = "member"
    test_db.commit()
    token = login_command(test_db, email, "Test1234").access_token

    response = client.post(
        "/invitations",
        json={"email": f"blocked-{suffix}@docpilot.ai"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_register_with_invitation_token(test_db, client):
    """Registering with a valid invitation token should join the correct org."""
    suffix = _uid()
    org = Organization(id=f"inv-org-{suffix}", slug=f"inv-org-{suffix}", name="Invite Org")
    test_db.add(org)
    test_db.flush()

    # Create an admin to issue the invite
    admin = User(id=f"inv-admin-{suffix}", email=f"admin-{suffix}@docpilot.ai",
                 display_name="Admin", password_hash="...", org_id=org.id,
                 role="admin", email_verified=True)
    test_db.add(admin)
    test_db.flush()
    test_db.add(OrganizationMembership(org_id=org.id, user_id=admin.id, role="owner"))
    test_db.commit()

    invitation = create_invitation_command(test_db, org.id, f"new-user-{suffix}@docpilot.ai", admin.id)

    # Register with the invitation token
    payload = UserRegister(
        email=f"new-user-{suffix}@docpilot.ai",
        display_name="New User",
        password="Test1234",
        invitation_token=invitation.token,
    )
    resp = client.post("/auth/register", json=payload.model_dump())
    assert resp.status_code == 201
    assert resp.json()["org_id"] == org.id

    # Invitation should be marked as accepted
    test_db.refresh(invitation)
    assert invitation.status == "accepted"
    membership = test_db.query(OrganizationMembership).filter_by(
        org_id=org.id,
        user_id=resp.json()["id"],
    ).one()
    assert membership.status == "active"
    assert membership.role == "member"


def test_accept_invitation_creates_membership_for_existing_user(test_db):
    suffix = _uid()
    existing_email = f"existing-{suffix}@docpilot.ai"
    register_user_command(
        test_db,
        UserRegister(
            email=existing_email,
            display_name="Existing User",
            password="Test1234",
        ),
    )
    existing_user = test_db.query(User).filter_by(email=existing_email).one()
    org = Organization(id=f"accept-org-{suffix}", slug=f"accept-org-{suffix}", name="Accept Org")
    owner = User(
        id=f"accept-owner-{suffix}",
        email=f"owner-{suffix}@docpilot.ai",
        display_name="Owner",
        password_hash="...",
        org_id=org.id,
        role="admin",
        email_verified=True,
    )
    test_db.add_all([org, owner])
    test_db.flush()
    test_db.add(OrganizationMembership(org_id=org.id, user_id=owner.id, role="owner"))
    test_db.commit()
    invitation = create_invitation_command(test_db, org.id, existing_email, owner.id)

    accepted = accept_invitation_command(test_db, invitation.token, existing_user.id)

    assert accepted is not None
    test_db.refresh(invitation)
    assert invitation.status == "accepted"
    membership = test_db.query(OrganizationMembership).filter_by(
        org_id=org.id,
        user_id=existing_user.id,
    ).one()
    assert membership.status == "active"
    assert membership.role == "member"


def test_register_with_new_org(test_db, client):
    """Registering with org_name + org_slug should create a new org."""
    suffix = _uid()
    payload = UserRegister(
        email=f"org-creator-{suffix}@docpilot.ai",
        display_name="Org Creator",
        password="Test1234",
        org_name=f"My Company {suffix}",
        org_slug=f"my-company-{suffix}",
    )
    resp = client.post("/auth/register", json=payload.model_dump())
    assert resp.status_code == 201
    data = resp.json()
    assert data["org_slug"] == f"my-company-{suffix}"

    # Verify the org was created
    org = test_db.query(Organization).filter_by(slug=f"my-company-{suffix}").first()
    assert org is not None
    assert org.name == f"My Company {suffix}"
    subscription = test_db.query(OrganizationSubscription).filter_by(org_id=org.id).one()
    assert subscription.plan == "starter"
    assert subscription.seat_limit == 1


def test_register_with_duplicate_org_slug(test_db, client):
    """Creating an org with duplicate slug should fail."""
    suffix = _uid()
    payload = UserRegister(
        email=f"dup1-{suffix}@docpilot.ai",
        display_name="Dup 1",
        password="Test1234",
        org_name=f"Dup Org {suffix}",
        org_slug=f"dup-org-{suffix}",
    )
    resp = client.post("/auth/register", json=payload.model_dump())
    assert resp.status_code == 201

    # Second user tries the same slug
    payload2 = UserRegister(
        email=f"dup2-{suffix}@docpilot.ai",
        display_name="Dup 2",
        password="Test1234",
        org_name="Dup Org 2",
        org_slug=f"dup-org-{suffix}",
    )
    resp = client.post("/auth/register", json=payload2.model_dump())
    assert resp.status_code == 400


def test_invitation_expired(test_db, client):
    """Expired invitations should be rejected."""
    suffix = _uid()
    from datetime import UTC, datetime, timedelta

    org = Organization(id=f"exp-org-{suffix}", slug=f"exp-org-{suffix}", name="Exp Org")
    test_db.add(org)
    test_db.flush()
    admin = User(id=f"exp-admin-{suffix}", email=f"exp-admin-{suffix}@docpilot.ai",
                 display_name="Admin", password_hash="...", org_id=org.id,
                 role="admin", email_verified=True)
    test_db.add(admin)
    test_db.commit()

    invitation = Invitation(
        id=f"exp-inv-{suffix}",
        org_id=org.id,
        invited_by=admin.id,
        email=f"expired-{suffix}@docpilot.ai",
        token=f"expired-token-{suffix}",
        status="pending",
        expires_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1),
    )
    test_db.add(invitation)
    test_db.commit()

    payload = UserRegister(
        email=f"expired-{suffix}@docpilot.ai",
        display_name="Expired",
        password="Test1234",
        invitation_token=invitation.token,
    )
    resp = client.post("/auth/register", json=payload.model_dump())
    assert resp.status_code == 400


def test_revoke_invitation(test_db, client):
    """Admin should be able to revoke an invitation."""
    suffix = _uid()
    email = f"rev-admin-{suffix}@docpilot.ai"
    from app.auth.service import _get_or_create_default_org, login_command
    _get_or_create_default_org(test_db)
    register_user_command(test_db, UserRegister(email=email, display_name="Rev Admin", password="Test1234"))
    u = test_db.query(User).filter_by(email=email).first()
    u.role = "admin"
    u.email_verified = True
    test_db.query(OrganizationMembership).filter_by(
        org_id=u.org_id,
        user_id=u.id,
    ).one().role = "admin"
    test_db.commit()
    token = login_command(test_db, email, "Test1234").access_token

    invite_email = f"rev-invitee-{suffix}@docpilot.ai"
    resp = client.post(
        "/invitations",
        json={"email": invite_email},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    inv_id = resp.json()["id"]

    resp = client.delete(
        f"/invitations/{inv_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    # Verify status changed
    inv = test_db.get(Invitation, inv_id)
    assert inv.status == "revoked"
