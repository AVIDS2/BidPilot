from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.access.service import require_project_capability
from app.audit.service import record_audit_event
from app.auth.schemas import CurrentUser
from app.models import OpportunityAssessment, OpportunityAssessmentDecision

from .schemas import (
    OpportunityAssessmentDecisionCreate,
    OpportunityAssessmentDecisionRead,
    OpportunityAssessmentRead,
    OpportunityAssessmentUpsert,
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _to_decision_read(item: OpportunityAssessmentDecision) -> OpportunityAssessmentDecisionRead:
    return OpportunityAssessmentDecisionRead(
        id=item.id,
        sequence=item.sequence,
        decision=item.decision,  # type: ignore[arg-type]
        rationale=item.rationale,
        scorecard_json=item.scorecard_json or {},
        risk_summary_json=item.risk_summary_json or {},
        decided_by_user_id=item.decided_by_user_id,
        created_at=item.created_at,
    )


def _to_read(item: OpportunityAssessment) -> OpportunityAssessmentRead:
    decisions = sorted(item.decisions, key=lambda decision: decision.sequence)
    return OpportunityAssessmentRead(
        id=item.id,
        project_id=item.project_id,
        status=item.status,  # type: ignore[arg-type]
        decision=item.decision,  # type: ignore[arg-type]
        scorecard_json=item.scorecard_json or {},
        risk_summary_json=item.risk_summary_json or {},
        rationale=item.rationale,
        created_by_user_id=item.created_by_user_id,
        decided_by_user_id=item.decided_by_user_id,
        decided_at=item.decided_at,
        lock_version=item.lock_version,
        created_at=item.created_at,
        updated_at=item.updated_at,
        decisions=[_to_decision_read(decision) for decision in decisions],
    )


def _load_for_project(
    db: Session,
    *,
    project_id: str,
    for_update: bool = False,
) -> OpportunityAssessment | None:
    statement = (
        select(OpportunityAssessment)
        .options(selectinload(OpportunityAssessment.decisions))
        .where(OpportunityAssessment.project_id == project_id)
        # A command can add a decision after this relationship was already
        # loaded in the current Session.  Reload it for the response rather
        # than returning a stale empty decision history to the API client.
        .execution_options(populate_existing=True)
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def get_opportunity_assessment_query(
    db: Session,
    *,
    project_id: str,
    current_user: CurrentUser,
) -> OpportunityAssessmentRead:
    require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.read",
    )
    assessment = _load_for_project(db, project_id=project_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Go/No-Go assessment not found")
    return _to_read(assessment)


def upsert_opportunity_assessment_command(
    db: Session,
    *,
    project_id: str,
    payload: OpportunityAssessmentUpsert,
    current_user: CurrentUser,
) -> OpportunityAssessmentRead:
    require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.manage",
    )
    assessment = _load_for_project(db, project_id=project_id, for_update=True)
    created = assessment is None
    if assessment is None:
        assessment = OpportunityAssessment(
            project_id=project_id,
            status=payload.status,
            scorecard_json=payload.scorecard_json,
            risk_summary_json=payload.risk_summary_json,
            rationale=payload.rationale,
            created_by_user_id=current_user.id,
        )
        db.add(assessment)
    else:
        if payload.lock_version is not None and assessment.lock_version != payload.lock_version:
            raise HTTPException(status_code=409, detail="Go/No-Go assessment was updated by another user")
        if assessment.decision != "pending" and payload.status == "draft":
            raise HTTPException(status_code=409, detail="A decided assessment cannot return to draft")
        assessment.status = payload.status
        assessment.scorecard_json = payload.scorecard_json
        assessment.risk_summary_json = payload.risk_summary_json
        assessment.rationale = payload.rationale
    db.flush()
    record_audit_event(
        db,
        project_id=project_id,
        event_type="opportunity.assessment_created" if created else "opportunity.assessment_updated",
        actor_type="user",
        actor_id=current_user.id,
        payload={"assessment_id": assessment.id, "status": assessment.status},
    )
    db.commit()
    refreshed = _load_for_project(db, project_id=project_id)
    assert refreshed is not None
    return _to_read(refreshed)


def decide_opportunity_command(
    db: Session,
    *,
    project_id: str,
    payload: OpportunityAssessmentDecisionCreate,
    current_user: CurrentUser,
) -> OpportunityAssessmentRead:
    require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.manage",
    )
    assessment = _load_for_project(db, project_id=project_id, for_update=True)
    if assessment is None:
        assessment = OpportunityAssessment(
            project_id=project_id,
            status="ready",
            created_by_user_id=current_user.id,
        )
        db.add(assessment)
        db.flush()
    if payload.lock_version is not None and assessment.lock_version != payload.lock_version:
        raise HTTPException(status_code=409, detail="Go/No-Go assessment was updated by another user")

    next_sequence = int(
        db.scalar(
            select(func.coalesce(func.max(OpportunityAssessmentDecision.sequence), 0)).where(
                OpportunityAssessmentDecision.assessment_id == assessment.id
            )
        )
        or 0
    ) + 1
    assessment.scorecard_json = payload.scorecard_json or assessment.scorecard_json or {}
    assessment.risk_summary_json = payload.risk_summary_json or assessment.risk_summary_json or {}
    assessment.rationale = payload.rationale if payload.rationale is not None else assessment.rationale
    assessment.status = "decided"
    assessment.decision = payload.decision
    assessment.decided_by_user_id = current_user.id
    assessment.decided_at = _now()
    decision = OpportunityAssessmentDecision(
        assessment_id=assessment.id,
        sequence=next_sequence,
        decision=payload.decision,
        rationale=payload.rationale,
        scorecard_json=assessment.scorecard_json or {},
        risk_summary_json=assessment.risk_summary_json or {},
        decided_by_user_id=current_user.id,
    )
    db.add(decision)
    db.flush()
    record_audit_event(
        db,
        project_id=project_id,
        event_type="opportunity.decision_recorded",
        actor_type="user",
        actor_id=current_user.id,
        payload={
            "assessment_id": assessment.id,
            "decision": payload.decision,
            "sequence": next_sequence,
        },
    )
    db.commit()
    refreshed = _load_for_project(db, project_id=project_id)
    assert refreshed is not None
    return _to_read(refreshed)
