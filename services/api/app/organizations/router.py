from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth, get_current_user_from_token, _get_org_slug, _get_user_plan, _user_to_current
from app.db import get_db

from .schemas import OrganizationCreate, OrganizationRead, OrganizationSwitchRequest
from .service import create_org_command, list_user_orgs_query, switch_user_org_command

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationRead, status_code=201)
def create_organization(
    payload: OrganizationCreate,
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> OrganizationRead:
    try:
        org = create_org_command(db, payload.name, payload.slug)
        # Assign the creator to the new org
        switch_user_org_command(db, current_user.id, org.id)
        return OrganizationRead(id=org.id, slug=org.slug, name=org.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[OrganizationRead])
def list_organizations(
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> list[OrganizationRead]:
    orgs = list_user_orgs_query(db, current_user.id)
    return [OrganizationRead(id=o.id, slug=o.slug, name=o.name) for o in orgs]


@router.post("/switch", response_model=CurrentUser)
def switch_organization(
    payload: OrganizationSwitchRequest,
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> CurrentUser:
    try:
        user = switch_user_org_command(db, current_user.id, payload.org_id)
        return _user_to_current(db, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
