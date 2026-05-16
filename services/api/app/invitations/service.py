import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Invitation, Organization, User

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
    user = db.query(User).filter_by(email=email, org_id=org_id).first()
    if user is not None:
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


def revoke_invitation_command(db: Session, invitation_id: str) -> None:
    invitation = db.get(Invitation, invitation_id)
    if invitation is None:
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


def accept_invitation_command(db: Session, token: str, user_id: str) -> Invitation | None:
    """Mark an invitation as accepted. Returns the invitation or None."""
    invitation = validate_invitation_token(db, token)
    if invitation is None:
        return None
    invitation.status = "accepted"
    db.commit()
    return invitation
