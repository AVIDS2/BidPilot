from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import get_current_user
from app.db import get_db

from .schemas import (
    RequirementBulkAssign,
    RequirementClaimCreate,
    RequirementClaimRead,
    RequirementDecisionCreate,
    RequirementDecisionRead,
    RequirementDetailRead,
    RequirementEvidenceLinkCreate,
    RequirementEvidenceLinkRead,
    RequirementEvidenceLinkUpdate,
    RequirementItemCreate,
    RequirementItemRead,
    RequirementItemUpdate,
)
from .service import (
    approve_requirement_decision_command,
    bulk_assign_requirements_command,
    create_requirement_claim_command,
    create_requirement_command,
    create_requirement_decision_command,
    get_requirement_query,
    link_evidence_command,
    list_requirements_query,
    update_requirement_command,
    update_evidence_link_command,
    verify_requirement_claim_command,
)

router = APIRouter(prefix="/requirements", tags=["requirements"])


@router.post("", response_model=RequirementItemRead, status_code=status.HTTP_201_CREATED)
def create_requirement(
    payload: RequirementItemCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RequirementItemRead:
    return create_requirement_command(
        db,
        payload,
        current_user=current_user,
        actor_id=current_user.id,
    )


@router.get("", response_model=list[RequirementItemRead])
def list_requirements(
    project_id: str,
    bid_category: str | None = None,
    coverage_status: str | None = None,
    evidence_status: str | None = None,
    risk_level: str | None = None,
    owner_user_id: str | None = None,
    verification_status: str | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[RequirementItemRead]:
    return list_requirements_query(
        db,
        project_id,
        current_user=current_user,
        bid_category=bid_category,
        coverage_status=coverage_status,
        evidence_status=evidence_status,
        risk_level=risk_level,
        owner_user_id=owner_user_id,
        verification_status=verification_status,
    )


@router.post("/bulk-assign", response_model=list[RequirementItemRead])
def bulk_assign_requirements(
    payload: RequirementBulkAssign,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[RequirementItemRead]:
    return bulk_assign_requirements_command(
        db,
        payload,
        current_user=current_user,
        actor_id=current_user.id,
    )


@router.get("/{requirement_id}", response_model=RequirementDetailRead)
def get_requirement(
    requirement_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RequirementDetailRead:
    return get_requirement_query(db, requirement_id, current_user=current_user)


@router.post(
    "/{requirement_id}/evidence",
    response_model=RequirementEvidenceLinkRead,
    status_code=status.HTTP_201_CREATED,
)
def link_requirement_evidence(
    requirement_id: str,
    payload: RequirementEvidenceLinkCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RequirementEvidenceLinkRead:
    return link_evidence_command(
        db,
        requirement_id,
        payload,
        current_user=current_user,
        actor_id=current_user.id,
    )


@router.patch(
    "/{requirement_id}/evidence/{link_id}",
    response_model=RequirementEvidenceLinkRead,
)
def update_requirement_evidence_link(
    requirement_id: str,
    link_id: str,
    payload: RequirementEvidenceLinkUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RequirementEvidenceLinkRead:
    return update_evidence_link_command(
        db,
        requirement_id,
        link_id,
        payload,
        current_user=current_user,
        actor_id=current_user.id,
    )


@router.post(
    "/{requirement_id}/decisions",
    response_model=RequirementDecisionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_requirement_decision(
    requirement_id: str,
    payload: RequirementDecisionCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RequirementDecisionRead:
    return create_requirement_decision_command(
        db,
        requirement_id,
        payload,
        current_user=current_user,
        actor_id=current_user.id,
    )


@router.post(
    "/{requirement_id}/decisions/{decision_id}/approve",
    response_model=RequirementDecisionRead,
)
def approve_requirement_decision(
    requirement_id: str,
    decision_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RequirementDecisionRead:
    return approve_requirement_decision_command(
        db,
        requirement_id,
        decision_id,
        current_user=current_user,
        actor_id=current_user.id,
    )


@router.post(
    "/{requirement_id}/claims",
    response_model=RequirementClaimRead,
    status_code=status.HTTP_201_CREATED,
)
def create_requirement_claim(
    requirement_id: str,
    payload: RequirementClaimCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RequirementClaimRead:
    return create_requirement_claim_command(
        db,
        requirement_id,
        payload,
        current_user=current_user,
        actor_id=current_user.id,
    )


@router.post(
    "/{requirement_id}/claims/{claim_id}/verify",
    response_model=RequirementClaimRead,
)
def verify_requirement_claim(
    requirement_id: str,
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RequirementClaimRead:
    return verify_requirement_claim_command(
        db,
        requirement_id,
        claim_id,
        current_user=current_user,
        actor_id=current_user.id,
    )


@router.patch("/{requirement_id}", response_model=RequirementItemRead)
def patch_requirement(
    requirement_id: str,
    payload: RequirementItemUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RequirementItemRead:
    return update_requirement_command(
        db,
        requirement_id,
        payload,
        current_user=current_user,
        actor_id=current_user.id,
    )


@router.put("/{requirement_id}", response_model=RequirementItemRead)
def update_requirement(
    requirement_id: str,
    payload: RequirementItemUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RequirementItemRead:
    return update_requirement_command(
        db,
        requirement_id,
        payload,
        current_user=current_user,
        actor_id=current_user.id,
    )
