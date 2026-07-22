from fastapi import APIRouter, Depends
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .schemas import OrganizationUsageBudgetRead, OrganizationUsageBudgetUpdate
from .service import (
    read_organization_usage_budget,
    update_organization_usage_budget,
    usage_quota_dict,
)

router = APIRouter(prefix="/usage", tags=["usage"], dependencies=[Depends(require_auth)])


@router.get("/quota")
def read_usage_quota(
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    return {
        "data": usage_quota_dict(
            db,
            org_id=current_user.org_id,
            actor_user_id=current_user.id,
        )
    }


@router.get("/budget", response_model=OrganizationUsageBudgetRead)
def read_usage_budget(
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> OrganizationUsageBudgetRead:
    return read_organization_usage_budget(
        db,
        org_id=current_user.org_id,
        actor_user_id=current_user.id,
    )


@router.put("/budget", response_model=OrganizationUsageBudgetRead)
def update_usage_budget(
    payload: OrganizationUsageBudgetUpdate,
    current_user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> OrganizationUsageBudgetRead:
    try:
        return update_organization_usage_budget(
            db,
            org_id=current_user.org_id,
            actor_user_id=current_user.id,
            updates={field: getattr(payload, field) for field in payload.model_fields_set},
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
