from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db

from .schemas import RequirementItemCreate, RequirementItemRead, RequirementItemUpdate
from .service import create_requirement_command, list_requirements_query, update_requirement_command

router = APIRouter(prefix="/requirements", tags=["requirements"])


@router.post("", response_model=RequirementItemRead, status_code=status.HTTP_201_CREATED)
def create_requirement(payload: RequirementItemCreate, db: Session = Depends(get_db)) -> RequirementItemRead:
    return create_requirement_command(db, payload)


@router.get("", response_model=list[RequirementItemRead])
def list_requirements(project_id: str, db: Session = Depends(get_db)) -> list[RequirementItemRead]:
    return list_requirements_query(db, project_id)


@router.put("/{requirement_id}", response_model=RequirementItemRead)
def update_requirement(requirement_id: str, payload: RequirementItemUpdate, db: Session = Depends(get_db)) -> RequirementItemRead:
    return update_requirement_command(db, requirement_id, payload)
