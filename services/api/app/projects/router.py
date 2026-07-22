from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth.service import require_auth, check_plan_limit
from app.auth.schemas import CurrentUser

from .schemas import (
    ProjectCreate,
    ProjectMemberCreate,
    ProjectMemberRead,
    ProjectMemberUpdate,
    ProjectRead,
    ProjectStatusUpdate,
)
from .service import (
    add_project_member_command,
    create_project_command,
    delete_project_command_for_user,
    get_project_query_for_user,
    list_project_members_query,
    list_projects_query_for_user,
    remove_project_member_command,
    update_project_member_command,
    update_project_status_command_for_user,
)
from .demo import create_demo_project_command

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), current_user: CurrentUser = Depends(require_auth)) -> ProjectRead:
    try:
        check_plan_limit(
            db,
            current_user.id,
            "projects",
            delta=1,
            org_id=current_user.org_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    org_id = current_user.org_id or "default"
    return create_project_command(db, payload, org_id, current_user.id)


@router.post("/demo", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_demo_project(
    response: Response,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> ProjectRead:
    project, created = create_demo_project_command(db, current_user)
    if not created:
        response.status_code = status.HTTP_200_OK
    return project


@router.get("", response_model=list[ProjectRead])
def list_projects(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[ProjectRead]:
    return list_projects_query_for_user(db, current_user)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db), current_user: CurrentUser = Depends(require_auth)) -> ProjectRead:
    return get_project_query_for_user(db, project_id, current_user)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: str,
    payload: ProjectStatusUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> ProjectRead:
    return update_project_status_command_for_user(db, project_id, payload.status, current_user)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_endpoint(project_id: str, db: Session = Depends(get_db), current_user: CurrentUser = Depends(require_auth)) -> None:
    delete_project_command_for_user(db, project_id, current_user)


@router.get("/{project_id}/members", response_model=list[ProjectMemberRead])
def list_project_members(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[ProjectMemberRead]:
    return list_project_members_query(db, project_id, current_user)


@router.post("/{project_id}/members", response_model=ProjectMemberRead, status_code=status.HTTP_201_CREATED)
def add_project_member(
    project_id: str,
    payload: ProjectMemberCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> ProjectMemberRead:
    return add_project_member_command(db, project_id, payload, current_user)


@router.patch("/{project_id}/members/{user_id}", response_model=ProjectMemberRead)
def update_project_member(
    project_id: str,
    user_id: str,
    payload: ProjectMemberUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> ProjectMemberRead:
    return update_project_member_command(db, project_id, user_id, payload, current_user)


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_member(
    project_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> None:
    remove_project_member_command(db, project_id, user_id, current_user)
