from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access.service import require_project_capability
from app.auth.schemas import CurrentUser
from app.models import (
    ResponsePlan,
    ResponsePlanEvidenceBinding,
    ResponsePlanRequirement,
    ResponsePlanSection,
)
from contracts.response_plans import get_response_plan, list_response_plans

from .schemas import (
    ResponsePlanDetailRead,
    ResponsePlanEvidenceBindingRead,
    ResponsePlanRead,
    ResponsePlanRequirementRead,
    ResponsePlanSectionRead,
)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(item for item in value if isinstance(item, str) and item))


def _plan_read(plan: ResponsePlan) -> ResponsePlanRead:
    return ResponsePlanRead(
        id=plan.id,
        project_id=plan.project_id,
        deliverable_id=plan.deliverable_id,
        version_number=plan.version_number,
        status=plan.status,
        source_fingerprint=plan.source_fingerprint,
        unmapped_requirement_ids=_string_list(plan.unmapped_requirement_ids_json),
        created_by_actor=plan.created_by_actor,
        created_at=plan.created_at,
    )


def _detail_read(db: Session, plan: ResponsePlan) -> ResponsePlanDetailRead:
    sections = list(
        db.scalars(
            select(ResponsePlanSection)
            .where(ResponsePlanSection.response_plan_id == plan.id)
            .order_by(
                ResponsePlanSection.sort_order_snapshot.asc(),
                ResponsePlanSection.id.asc(),
            )
        ).all()
    )
    section_reads: list[ResponsePlanSectionRead] = []
    for section in sections:
        requirements = list(
            db.scalars(
                select(ResponsePlanRequirement)
                .where(ResponsePlanRequirement.response_plan_section_id == section.id)
                .order_by(ResponsePlanRequirement.requirement_id.asc())
            ).all()
        )
        bindings = list(
            db.scalars(
                select(ResponsePlanEvidenceBinding)
                .where(ResponsePlanEvidenceBinding.response_plan_section_id == section.id)
                .order_by(
                    ResponsePlanEvidenceBinding.generation_iteration.desc(),
                    ResponsePlanEvidenceBinding.created_at.desc(),
                )
            ).all()
        )
        section_reads.append(
            ResponsePlanSectionRead(
                id=section.id,
                deliverable_section_id=section.deliverable_section_id,
                section_key=section.section_key,
                title=section.title_snapshot,
                sort_order=section.sort_order_snapshot,
                status=section.status,
                requirements=[
                    ResponsePlanRequirementRead(
                        id=requirement.id,
                        requirement_id=requirement.requirement_id,
                        requirement_lock_version=requirement.requirement_lock_version,
                        requirement_text=requirement.requirement_text_snapshot,
                        priority=requirement.priority_snapshot,
                        owner_user_id=requirement.owner_user_id_snapshot,
                        verification_status=requirement.verification_status_snapshot,
                        assignment_reason=requirement.assignment_reason,
                    )
                    for requirement in requirements
                ],
                evidence_bindings=[
                    ResponsePlanEvidenceBindingRead(
                        id=binding.id,
                        evidence_set_id=binding.evidence_set_id,
                        execution_run_id=binding.execution_run_id,
                        generation_iteration=binding.generation_iteration,
                        evidence_set_status=binding.evidence_set_status,
                        unmet_requirement_ids=_string_list(
                            binding.unmet_requirement_ids_json
                        ),
                        degraded_reasons=_string_list(binding.degraded_reasons_json),
                        content_plan=dict(binding.content_plan_json or {}),
                        created_at=binding.created_at,
                    )
                    for binding in bindings
                ],
            )
        )
    base = _plan_read(plan)
    return ResponsePlanDetailRead(**base.model_dump(), sections=section_reads)


def list_response_plans_query(
    db: Session,
    project_id: str,
    current_user: CurrentUser,
) -> list[ResponsePlanRead]:
    require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.read",
    )
    return [_plan_read(plan) for plan in list_response_plans(db, project_id=project_id)]


def get_response_plan_query(
    db: Session,
    *,
    project_id: str,
    response_plan_id: str,
    current_user: CurrentUser,
) -> ResponsePlanDetailRead:
    require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.read",
    )
    plan = get_response_plan(
        db,
        response_plan_id=response_plan_id,
        project_id=project_id,
    )
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="response_plan_not_found")
    return _detail_read(db, plan)
