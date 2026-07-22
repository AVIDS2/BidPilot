from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth, _user_to_current
from app.db import get_db
from app.entitlements.schemas import OrganizationEntitlementRead
from app.entitlements.service import resolve_org_entitlements
from app.models import OrganizationSubscription

from .schemas import (
    OrganizationBillingOwnerTransfer,
    OrganizationCreate,
    OrganizationMemberRead,
    OrganizationMemberRemovalRead,
    OrganizationMemberRoleUpdate,
    OrganizationRead,
    OrganizationSwitchRequest,
)
from .service import (
    MEMBERSHIP_ROLES,
    create_org_for_user_command,
    list_org_members_query,
    list_user_orgs_query,
    OrganizationMembershipConflict,
    OrganizationMembershipNotFound,
    remove_organization_member_command,
    require_organization_role,
    switch_user_org_command,
    transfer_organization_billing_owner_command,
    update_organization_membership_role_command,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _member_to_read(
    *,
    membership,
    user,
    billing_owner_user_id: str | None,
) -> OrganizationMemberRead:
    return OrganizationMemberRead(
        id=user.id,
        display_name=user.display_name,
        email=user.email,
        role=membership.role,
        is_billing_owner=billing_owner_user_id == user.id,
    )


def _organization_to_read(org) -> OrganizationRead:
    return OrganizationRead(id=org.id, slug=org.slug, name=org.name)


@router.post("", response_model=OrganizationRead, status_code=201)
def create_organization(
    payload: OrganizationCreate,
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> OrganizationRead:
    try:
        org, _user = create_org_for_user_command(
            db,
            name=payload.name,
            slug=payload.slug,
            user_id=current_user.id,
        )
        return _organization_to_read(org)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[OrganizationRead])
def list_organizations(
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> list[OrganizationRead]:
    orgs = list_user_orgs_query(db, current_user.id)
    return [_organization_to_read(org) for org in orgs]


@router.get("/current/members", response_model=list[OrganizationMemberRead])
def list_current_organization_members(
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> list[OrganizationMemberRead]:
    try:
        require_organization_role(
            db,
            org_id=current_user.org_id,
            user_id=current_user.id,
            allowed_roles=MEMBERSHIP_ROLES,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Organization access denied") from exc
    subscription = db.query(OrganizationSubscription).filter_by(org_id=current_user.org_id).first()
    billing_owner_user_id = subscription.billing_owner_user_id if subscription else None
    return [
        _member_to_read(
            membership=membership,
            user=user,
            billing_owner_user_id=billing_owner_user_id,
        )
        for membership, user in list_org_members_query(db, current_user.org_id)
    ]


@router.patch("/current/members/{member_user_id}", response_model=OrganizationMemberRead)
def update_current_organization_member_role(
    member_user_id: str,
    payload: OrganizationMemberRoleUpdate,
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> OrganizationMemberRead:
    try:
        membership = update_organization_membership_role_command(
            db,
            org_id=current_user.org_id,
            actor_user_id=current_user.id,
            target_user_id=member_user_id,
            role=payload.role,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except OrganizationMembershipNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OrganizationMembershipConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    member = next(
        (
            user
            for candidate_membership, user in list_org_members_query(db, current_user.org_id)
            if candidate_membership.id == membership.id
        ),
        None,
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Organization member not found")
    subscription = db.query(OrganizationSubscription).filter_by(org_id=current_user.org_id).first()
    return _member_to_read(
        membership=membership,
        user=member,
        billing_owner_user_id=subscription.billing_owner_user_id if subscription else None,
    )


@router.post("/current/billing-owner", response_model=OrganizationMemberRead)
def transfer_current_organization_billing_owner(
    payload: OrganizationBillingOwnerTransfer,
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> OrganizationMemberRead:
    try:
        subscription = transfer_organization_billing_owner_command(
            db,
            org_id=current_user.org_id,
            actor_user_id=current_user.id,
            target_user_id=payload.user_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except OrganizationMembershipConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    for membership, user in list_org_members_query(db, current_user.org_id):
        if user.id == payload.user_id:
            return _member_to_read(
                membership=membership,
                user=user,
                billing_owner_user_id=subscription.billing_owner_user_id,
            )
    raise HTTPException(status_code=404, detail="Organization member not found")


@router.delete("/current/members/{member_user_id}", response_model=OrganizationMemberRemovalRead)
def remove_current_organization_member(
    member_user_id: str,
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> OrganizationMemberRemovalRead:
    try:
        outcome = remove_organization_member_command(
            db,
            org_id=current_user.org_id,
            actor_user_id=current_user.id,
            target_user_id=member_user_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except OrganizationMembershipNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OrganizationMembershipConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return OrganizationMemberRemovalRead(
        user_id=outcome.user_id,
        active_org=_organization_to_read(outcome.active_org),
        personal_workspace_created=outcome.personal_workspace_created,
    )


@router.get("/current/entitlements", response_model=OrganizationEntitlementRead)
def get_current_organization_entitlements(
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> OrganizationEntitlementRead:
    return resolve_org_entitlements(
        db,
        org_id=current_user.org_id,
        actor_user_id=current_user.id,
    ).to_read()


@router.post("/switch", response_model=CurrentUser)
def switch_organization(
    payload: OrganizationSwitchRequest,
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> CurrentUser:
    try:
        user = switch_user_org_command(db, current_user.id, payload.org_id)
        return _user_to_current(db, user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
