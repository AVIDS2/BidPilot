import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Invitation, OrganizationMembership, User
from app.organizations.service import (
    ACTIVE_MEMBERSHIP_STATUS,
    create_organization_membership_command,
)

INVITATION_EXPIRES_DAYS = 7


def _make_token() -> str:
    return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:32]


def create_invitation_command(db: Session, org_id: str, email: str, invited_by_id: str) -> Invitation:
    """Create a pending invitation. Raises ValueError if email already invited."""
    # Check for existing pending invitation for this email in this org
    existing = db.query(Invitation).filter_by(
        org_id=org_id, email=email, status="pending"
    ).first()
    if existing is not None and existing.expires_at > datetime.now(UTC).replace(tzinfo=None):
        raise ValueError("An active invitation already exists for this email")

    # Check if user is already in the org
    member_user_id = db.scalar(
        select(OrganizationMembership.user_id)
        .join(User, User.id == OrganizationMembership.user_id)
        .where(
            User.email == email,
            OrganizationMembership.org_id == org_id,
            OrganizationMembership.status == ACTIVE_MEMBERSHIP_STATUS,
        )
    )
    if member_user_id is not None:
        raise ValueError("User is already a member of this organization")

    token = _make_token()
    invitation = Invitation(
        org_id=org_id,
        invited_by=invited_by_id,
        email=email,
        token=token,
        status="pending",
        expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=INVITATION_EXPIRES_DAYS),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return invitation


def list_invitations_query(db: Session, org_id: str) -> list[Invitation]:
    return db.query(Invitation).filter_by(org_id=org_id, status="pending").order_by(Invitation.created_at.desc()).all()


def revoke_invitation_command(
    db: Session,
    invitation_id: str,
    *,
    org_id: str | None = None,
) -> None:
    invitation = db.get(Invitation, invitation_id)
    if invitation is None or (org_id is not None and invitation.org_id != org_id):
        raise ValueError("Invitation not found")
    invitation.status = "revoked"
    db.commit()


def validate_invitation_token(db: Session, token: str) -> Invitation | None:
    """Return a valid pending invitation for the given token, or None."""
    invitation = db.query(Invitation).filter_by(token=token, status="pending").first()
    if invitation is None:
        return None
    if invitation.expires_at < datetime.now(UTC).replace(tzinfo=None):
        invitation.status = "expired"
        db.commit()
        return None
    return invitation


def accept_invitation_command(
    db: Session,
    token: str,
    user_id: str,
    *,
    commit: bool = True,
) -> Invitation | None:
    """Mark an invitation as accepted. Returns the invitation or None."""
    invitation = validate_invitation_token(db, token)
    if invitation is None:
        return None
    user = db.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    if user.email.casefold() != invitation.email.casefold():
        raise ValueError("Invitation email does not match user email")
    create_organization_membership_command(
        db,
        org_id=invitation.org_id,
        user_id=user_id,
        role="member",
        commit=False,
    )
    invitation.status = "accepted"
    if commit:
        db.commit()
        db.refresh(invitation)
    return invitation
