from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .schemas import ResponsePlanDetailRead, ResponsePlanRead
from .service import get_response_plan_query, list_response_plans_query

router = APIRouter(prefix="/response-plans", tags=["response-plans"])


@router.get("", response_model=list[ResponsePlanRead])
def list_response_plans_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[ResponsePlanRead]:
    return list_response_plans_query(db, project_id, current_user)


@router.get("/{response_plan_id}", response_model=ResponsePlanDetailRead)
def get_response_plan_endpoint(
    response_plan_id: str,
    project_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> ResponsePlanDetailRead:
    return get_response_plan_query(
        db,
        project_id=project_id,
        response_plan_id=response_plan_id,
        current_user=current_user,
    )
