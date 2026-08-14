from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .schemas import (
    OpportunityAssessmentDecisionCreate,
    OpportunityAssessmentRead,
    OpportunityAssessmentUpsert,
)
from .service import (
    decide_opportunity_command,
    get_opportunity_assessment_query,
    upsert_opportunity_assessment_command,
)


router = APIRouter(prefix="/opportunities", tags=["opportunities"])


@router.get("/projects/{project_id}/assessment", response_model=OpportunityAssessmentRead)
def get_assessment(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> OpportunityAssessmentRead:
    return get_opportunity_assessment_query(db, project_id=project_id, current_user=current_user)


@router.put("/projects/{project_id}/assessment", response_model=OpportunityAssessmentRead)
def upsert_assessment(
    project_id: str,
    payload: OpportunityAssessmentUpsert,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> OpportunityAssessmentRead:
    return upsert_opportunity_assessment_command(
        db,
        project_id=project_id,
        payload=payload,
        current_user=current_user,
    )


@router.post("/projects/{project_id}/assessment/decisions", response_model=OpportunityAssessmentRead)
def record_decision(
    project_id: str,
    payload: OpportunityAssessmentDecisionCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> OpportunityAssessmentRead:
    return decide_opportunity_command(
        db,
        project_id=project_id,
        payload=payload,
        current_user=current_user,
    )
