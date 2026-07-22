from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db
from app.email.service import send_invitation_email
from app.organizations.service import MEMBERSHIP_MANAGERS, require_organization_role

from .schemas import InvitationCreate, InvitationRead
from .service import (
    create_invitation_command, list_invitations_query, revoke_invitation_command
)

router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.post("", response_model=InvitationRead, status_code=201)
def create_invitation(
    payload: InvitationCreate,
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> InvitationRead:
    try:
        require_organization_role(
            db,
            org_id=current_user.org_id,
            user_id=current_user.id,
            allowed_roles=MEMBERSHIP_MANAGERS,
        )
        invitation = create_invitation_command(db, current_user.org_id, payload.email, current_user.id)
        # Send invitation email (non-blocking)
        send_invitation_email(payload.email, invitation.token, current_user.org_slug)
        return InvitationRead(
            id=invitation.id,
            org_id=invitation.org_id,
            email=invitation.email,
            status=invitation.status,
            created_at=str(invitation.created_at) if invitation.created_at else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("", response_model=list[InvitationRead])
def list_invitations(
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> list[InvitationRead]:
    try:
        require_organization_role(
            db,
            org_id=current_user.org_id,
            user_id=current_user.id,
            allowed_roles=MEMBERSHIP_MANAGERS,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    invitations = list_invitations_query(db, current_user.org_id)
    return [
        InvitationRead(
            id=i.id,
            org_id=i.org_id,
            email=i.email,
            status=i.status,
            created_at=str(i.created_at) if i.created_at else None,
        )
        for i in invitations
    ]


@router.delete("/{invitation_id}", status_code=204)
def revoke_invitation(
    invitation_id: str,
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> None:
    try:
        require_organization_role(
            db,
            org_id=current_user.org_id,
            user_id=current_user.id,
            allowed_roles=MEMBERSHIP_MANAGERS,
        )
        revoke_invitation_command(db, invitation_id, org_id=current_user.org_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
