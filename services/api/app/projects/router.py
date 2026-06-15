from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.auth.service import require_auth, check_plan_limit
from app.auth.schemas import CurrentUser

from .schemas import ProjectCreate, ProjectRead, ProjectStatusUpdate
from .service import (
    create_project_command,
    delete_project_command_for_org,
    get_project_query_for_org,
    list_projects_query,
    update_project_status_command_for_org,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), current_user: CurrentUser = Depends(require_auth)) -> ProjectRead:
    try:
        check_plan_limit(db, current_user.id, "projects", delta=1, plan=current_user.plan)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    org_id = current_user.org_id or "default"
    return create_project_command(db, payload, org_id)


@router.get("", response_model=list[ProjectRead])
def list_projects(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[ProjectRead]:
    return list_projects_query(db, current_user.org_id or None)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db), current_user: CurrentUser = Depends(require_auth)) -> ProjectRead:
    result = get_project_query_for_org(db, project_id, current_user.org_id or "default")
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: str,
    payload: ProjectStatusUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> ProjectRead:
    result = update_project_status_command_for_org(db, project_id, current_user.org_id or "default", payload.status)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_endpoint(project_id: str, db: Session = Depends(get_db), current_user: CurrentUser = Depends(require_auth)) -> None:
    if not delete_project_command_for_org(db, project_id, current_user.org_id or "default"):
        raise HTTPException(status_code=404, detail="Project not found")
