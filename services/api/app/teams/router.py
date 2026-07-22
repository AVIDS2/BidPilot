from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db
from app.models import User
from app.organizations.service import (
    MEMBERSHIP_MANAGERS,
    MEMBERSHIP_ROLES,
    require_organization_role,
)

from .schemas import TeamCreate, TeamUpdate, TeamMemberAdd, TeamRead, TeamMemberRead, TeamListResponse
from .service import (
    create_team_command, list_teams_query, get_team_by_id,
    update_team_command, delete_team_command,
    add_team_member_command, remove_team_member_command, list_team_members_query,
)

router = APIRouter(prefix="/teams", tags=["teams"])


def _require_workspace_role(
    db: Session,
    current_user: CurrentUser,
    allowed_roles: set[str],
) -> None:
    try:
        require_organization_role(
            db,
            org_id=current_user.org_id,
            user_id=current_user.id,
            allowed_roles=allowed_roles,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Workspace role required") from exc


def _team_to_read(team, members: list) -> TeamRead:
    return TeamRead(
        id=team.id,
        org_id=team.org_id,
        name=team.name,
        slug=team.slug,
        created_at=team.created_at,
        members=[
            TeamMemberRead(
                id=m.id,
                user_id=m.user_id,
                user_email=m.user.email if m.user else "",
                user_display_name=m.user.display_name if m.user else "",
                role=m.role,
                created_at=m.created_at,
            )
            for m in members
        ],
    )


@router.post("", response_model=TeamRead, status_code=201)
def create_team(
    payload: TeamCreate,
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> TeamRead:
    try:
        _require_workspace_role(db, current_user, MEMBERSHIP_MANAGERS)
        team = create_team_command(db, current_user.org_id, payload.name, payload.slug)
        return _team_to_read(team, [])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=TeamListResponse)
def list_teams(
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> TeamListResponse:
    _require_workspace_role(db, current_user, MEMBERSHIP_ROLES)
    teams = list_teams_query(db, current_user.org_id)
    items = []
    for t in teams:
        members = list_team_members_query(db, t.id)
        items.append(_team_to_read(t, members))
    return TeamListResponse(items=items, total=len(items))


@router.get("/{team_id}", response_model=TeamRead)
def get_team(
    team_id: str,
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> TeamRead:
    _require_workspace_role(db, current_user, MEMBERSHIP_ROLES)
    team = get_team_by_id(db, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    if team.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    members = list_team_members_query(db, team_id)
    return _team_to_read(team, members)


@router.patch("/{team_id}", response_model=TeamRead)
def update_team(
    team_id: str,
    payload: TeamUpdate,
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> TeamRead:
    _require_workspace_role(db, current_user, MEMBERSHIP_MANAGERS)
    team = get_team_by_id(db, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    if team.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        updated = update_team_command(db, team_id, payload.name)
        members = list_team_members_query(db, team_id)
        return _team_to_read(updated, members)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{team_id}", status_code=204)
def delete_team(
    team_id: str,
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> None:
    _require_workspace_role(db, current_user, MEMBERSHIP_MANAGERS)
    team = get_team_by_id(db, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    if team.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        delete_team_command(db, team_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{team_id}/members", response_model=TeamMemberRead, status_code=201)
def add_member(
    team_id: str,
    payload: TeamMemberAdd,
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> TeamMemberRead:
    _require_workspace_role(db, current_user, MEMBERSHIP_MANAGERS)
    team = get_team_by_id(db, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    if team.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        member = add_team_member_command(db, team_id, payload.user_id, payload.role)
        user = db.get(User, member.user_id)
        return TeamMemberRead(
            id=member.id,
            user_id=member.user_id,
            user_email=user.email if user else "",
            user_display_name=user.display_name if user else "",
            role=member.role,
            created_at=member.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{team_id}/members/{user_id}", status_code=204)
def remove_member(
    team_id: str,
    user_id: str,
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> None:
    _require_workspace_role(db, current_user, MEMBERSHIP_MANAGERS)
    team = get_team_by_id(db, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    if team.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        remove_team_member_command(db, team_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
