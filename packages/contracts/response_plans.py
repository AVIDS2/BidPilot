"""Durable response-plan revisions shared by the API and LangGraph worker.

The execution graph may checkpoint a short-lived content plan, but proposal
business truth must survive outside that checkpoint.  This module turns the
current deliverable outline and requirement ledger into immutable response
plan revisions, then binds each draft attempt to the exact evidence set and
writing plan it used.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import (
    Deliverable,
    DeliverableSection,
    EvidenceSet,
    ExecutionRun,
    Project,
    RequirementItem,
    ResponsePlan,
    ResponsePlanEvidenceBinding,
    ResponsePlanRequirement,
    ResponsePlanSection,
)


class ResponsePlanScopeError(ValueError):
    """Raised when a plan, run, evidence set, or section crosses its scope."""


@dataclass(frozen=True)
class ResponsePlanSectionSnapshot:
    response_plan_id: str
    response_plan_version: int
    response_plan_section_id: str
    deliverable_section_id: str
    section_key: str
    requirements: tuple[dict[str, Any], ...]
    unmapped_requirement_ids: tuple[str, ...]


@dataclass(frozen=True)
class ResponsePlanBindingSnapshot:
    response_plan_id: str
    response_plan_version: int
    response_plan_section_id: str
    deliverable_section_id: str
    response_plan_evidence_binding_id: str
    section_key: str
    evidence_set_id: str
    execution_run_id: str
    generation_iteration: int
    evidence_set_status: str
    unmet_requirement_ids: tuple[str, ...]
    degraded_reasons: tuple[str, ...]
    content_plan: dict[str, Any]
    requirements: tuple[dict[str, Any], ...]


def _json_copy(value: dict[str, Any]) -> dict[str, Any]:
    """Reject non-JSON graph values before making a durable plan snapshot."""
    try:
        copied = json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))
    except (TypeError, ValueError) as exc:
        raise ResponsePlanScopeError("content_plan_not_json_serializable") from exc
    if not isinstance(copied, dict):
        raise ResponsePlanScopeError("content_plan_invalid")
    return copied


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(dict.fromkeys(item for item in value if isinstance(item, str) and item))


def _require_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise ResponsePlanScopeError("response_plan_project_not_found")
    return project


def _find_or_create_section(
    db: Session,
    *,
    project_id: str,
    section_key: str,
) -> DeliverableSection:
    section = db.scalar(
        select(DeliverableSection)
        .join(Deliverable, Deliverable.id == DeliverableSection.deliverable_id)
        .where(
            Deliverable.project_id == project_id,
            DeliverableSection.section_key == section_key,
        )
        .order_by(Deliverable.id.asc(), DeliverableSection.sort_order.asc())
        .limit(1)
    )
    if section is not None:
        return section

    deliverable = db.scalar(
        select(Deliverable)
        .where(Deliverable.project_id == project_id)
        .order_by(Deliverable.id.asc())
        .limit(1)
    )
    if deliverable is None:
        deliverable = Deliverable(
            project_id=project_id,
            type="proposal",
            title=f"Deliverable for {section_key}",
            status="draft",
        )
        db.add(deliverable)
        db.flush()

    next_order = db.scalar(
        select(func.max(DeliverableSection.sort_order)).where(
            DeliverableSection.deliverable_id == deliverable.id
        )
    )
    section = DeliverableSection(
        deliverable_id=deliverable.id,
        section_key=section_key,
        title=section_key.replace("-", " ").title(),
        status="draft",
        assignee_type="ai",
        sort_order=int(next_order or 0) + 1,
    )
    db.add(section)
    db.flush()
    return section


def _deliverable_sections(db: Session, deliverable_id: str) -> list[DeliverableSection]:
    return list(
        db.scalars(
            select(DeliverableSection)
            .where(DeliverableSection.deliverable_id == deliverable_id)
            .order_by(DeliverableSection.sort_order.asc(), DeliverableSection.id.asc())
        ).all()
    )


def _project_requirements(db: Session, project_id: str) -> list[RequirementItem]:
    return list(
        db.scalars(
            select(RequirementItem)
            .where(RequirementItem.project_id == project_id)
            .order_by(RequirementItem.section_key.asc(), RequirementItem.id.asc())
        ).all()
    )


def _fingerprint(
    sections: list[DeliverableSection],
    requirements: list[RequirementItem],
) -> str:
    payload = {
        "sections": [
            {
                "id": section.id,
                "section_key": section.section_key,
                "title": section.title,
                "sort_order": section.sort_order,
            }
            for section in sections
        ],
        "requirements": [
            {
                "id": requirement.id,
                "section_key": requirement.section_key,
                "requirement_text": requirement.requirement_text,
                "priority": requirement.priority,
                "owner_user_id": requirement.owner_user_id,
                "verification_status": requirement.verification_status,
                "lock_version": requirement.lock_version,
            }
            for requirement in requirements
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _active_plan(
    db: Session,
    *,
    project_id: str,
    deliverable_id: str,
    source_fingerprint: str,
) -> ResponsePlan | None:
    return db.scalar(
        select(ResponsePlan)
        .where(
            ResponsePlan.project_id == project_id,
            ResponsePlan.deliverable_id == deliverable_id,
            ResponsePlan.status == "active",
            ResponsePlan.source_fingerprint == source_fingerprint,
        )
        .order_by(ResponsePlan.version_number.desc())
        .limit(1)
    )


def _create_plan_revision(
    db: Session,
    *,
    project_id: str,
    deliverable_id: str,
    source_fingerprint: str,
    sections: list[DeliverableSection],
    requirements: list[RequirementItem],
) -> ResponsePlan:
    for prior in db.scalars(
        select(ResponsePlan).where(
            ResponsePlan.project_id == project_id,
            ResponsePlan.deliverable_id == deliverable_id,
            ResponsePlan.status == "active",
        )
    ).all():
        prior.status = "superseded"

    version_number = int(
        db.scalar(
            select(func.max(ResponsePlan.version_number)).where(
                ResponsePlan.deliverable_id == deliverable_id
            )
        )
        or 0
    ) + 1
    section_keys = {section.section_key for section in sections}
    unmapped_requirement_ids = [
        requirement.id
        for requirement in requirements
        if requirement.section_key not in section_keys
    ]
    response_plan = ResponsePlan(
        project_id=project_id,
        deliverable_id=deliverable_id,
        version_number=version_number,
        status="active",
        source_fingerprint=source_fingerprint,
        unmapped_requirement_ids_json=unmapped_requirement_ids,
        created_by_actor="workflow",
    )
    db.add(response_plan)
    db.flush()

    requirements_by_section: dict[str, list[RequirementItem]] = {}
    for requirement in requirements:
        requirements_by_section.setdefault(requirement.section_key, []).append(requirement)

    for section in sections:
        plan_section = ResponsePlanSection(
            response_plan_id=response_plan.id,
            deliverable_section_id=section.id,
            section_key=section.section_key,
            title_snapshot=section.title,
            sort_order_snapshot=section.sort_order,
            status="planned",
        )
        db.add(plan_section)
        db.flush()
        for requirement in requirements_by_section.get(section.section_key, []):
            db.add(
                ResponsePlanRequirement(
                    response_plan_section_id=plan_section.id,
                    requirement_id=requirement.id,
                    requirement_lock_version=requirement.lock_version,
                    requirement_text_snapshot=requirement.requirement_text,
                    priority_snapshot=requirement.priority,
                    owner_user_id_snapshot=requirement.owner_user_id,
                    verification_status_snapshot=requirement.verification_status,
                    assignment_reason="section_key_exact_match",
                )
            )
    db.flush()
    return response_plan


def _plan_section_snapshot(
    db: Session,
    *,
    response_plan: ResponsePlan,
    deliverable_section_id: str,
) -> ResponsePlanSectionSnapshot:
    plan_section = db.scalar(
        select(ResponsePlanSection).where(
            ResponsePlanSection.response_plan_id == response_plan.id,
            ResponsePlanSection.deliverable_section_id == deliverable_section_id,
        )
    )
    if plan_section is None:
        raise ResponsePlanScopeError("response_plan_section_missing")
    assignments = list(
        db.scalars(
            select(ResponsePlanRequirement)
            .where(ResponsePlanRequirement.response_plan_section_id == plan_section.id)
            .order_by(ResponsePlanRequirement.requirement_id.asc())
        ).all()
    )
    requirements = tuple(
        {
            "id": assignment.requirement_id,
            "section_key": plan_section.section_key,
            "requirement_text": assignment.requirement_text_snapshot,
            "priority": assignment.priority_snapshot,
            "owner_user_id": assignment.owner_user_id_snapshot,
            "verification_status": assignment.verification_status_snapshot,
            "lock_version": assignment.requirement_lock_version,
        }
        for assignment in assignments
    )
    return ResponsePlanSectionSnapshot(
        response_plan_id=response_plan.id,
        response_plan_version=response_plan.version_number,
        response_plan_section_id=plan_section.id,
        deliverable_section_id=plan_section.deliverable_section_id,
        section_key=plan_section.section_key,
        requirements=requirements,
        unmapped_requirement_ids=_string_list(response_plan.unmapped_requirement_ids_json),
    )


def ensure_response_plan_section(
    db: Session,
    *,
    project_id: str,
    section_key: str,
) -> ResponsePlanSectionSnapshot:
    """Resolve the immutable structural plan revision for a draft section."""
    _require_project(db, project_id)
    section = _find_or_create_section(db, project_id=project_id, section_key=section_key)
    deliverable = db.get(Deliverable, section.deliverable_id)
    if deliverable is None or deliverable.project_id != project_id:
        raise ResponsePlanScopeError("response_plan_deliverable_scope_invalid")

    sections = _deliverable_sections(db, deliverable.id)
    requirements = _project_requirements(db, project_id)
    source_fingerprint = _fingerprint(sections, requirements)
    response_plan = _active_plan(
        db,
        project_id=project_id,
        deliverable_id=deliverable.id,
        source_fingerprint=source_fingerprint,
    )
    if response_plan is None:
        try:
            with db.begin_nested():
                response_plan = _create_plan_revision(
                    db,
                    project_id=project_id,
                    deliverable_id=deliverable.id,
                    source_fingerprint=source_fingerprint,
                    sections=sections,
                    requirements=requirements,
                )
        except IntegrityError:
            response_plan = _active_plan(
                db,
                project_id=project_id,
                deliverable_id=deliverable.id,
                source_fingerprint=source_fingerprint,
            )
            if response_plan is None:
                raise
    return _plan_section_snapshot(
        db,
        response_plan=response_plan,
        deliverable_section_id=section.id,
    )


def capture_response_plan_binding(
    db: Session,
    *,
    project_id: str,
    execution_run_id: str,
    evidence_set_id: str,
    response_plan_section_id: str,
    generation_iteration: int,
    content_plan: dict[str, Any],
) -> ResponsePlanBindingSnapshot:
    """Persist an idempotent plan/evidence binding for one draft candidate."""
    if generation_iteration < 1:
        raise ResponsePlanScopeError("response_plan_generation_iteration_invalid")
    run = db.get(ExecutionRun, execution_run_id)
    evidence_set = db.get(EvidenceSet, evidence_set_id)
    plan_section = db.get(ResponsePlanSection, response_plan_section_id)
    if run is None or run.project_id != project_id:
        raise ResponsePlanScopeError("response_plan_execution_run_scope_invalid")
    if evidence_set is None:
        raise ResponsePlanScopeError("response_plan_evidence_set_not_found")
    if plan_section is None:
        raise ResponsePlanScopeError("response_plan_section_not_found")
    response_plan = db.get(ResponsePlan, plan_section.response_plan_id)
    if response_plan is None or response_plan.project_id != project_id:
        raise ResponsePlanScopeError("response_plan_project_scope_invalid")
    if (
        evidence_set.project_id != project_id
        or evidence_set.execution_run_id != execution_run_id
        or evidence_set.section_key != plan_section.section_key
    ):
        raise ResponsePlanScopeError("response_plan_evidence_set_scope_invalid")
    if evidence_set.status == "invalidated":
        raise ResponsePlanScopeError("response_plan_evidence_set_invalidated")

    existing = db.scalar(
        select(ResponsePlanEvidenceBinding).where(
            ResponsePlanEvidenceBinding.execution_run_id == execution_run_id,
            ResponsePlanEvidenceBinding.generation_iteration == generation_iteration,
        )
    )
    if existing is not None:
        if (
            existing.response_plan_section_id != response_plan_section_id
            or existing.evidence_set_id != evidence_set_id
        ):
            raise ResponsePlanScopeError("response_plan_binding_replay_scope_invalid")
        return load_authorized_response_plan_binding(
            db,
            response_plan_evidence_binding_id=existing.id,
            project_id=project_id,
            execution_run_id=execution_run_id,
            section_key=plan_section.section_key,
        )

    binding = ResponsePlanEvidenceBinding(
        response_plan_section_id=response_plan_section_id,
        evidence_set_id=evidence_set_id,
        execution_run_id=execution_run_id,
        generation_iteration=generation_iteration,
        content_plan_json=_json_copy(content_plan),
        evidence_set_status=evidence_set.status,
        unmet_requirement_ids_json=list(_string_list(evidence_set.unmet_requirement_ids_json)),
        degraded_reasons_json=list(
            dict.fromkeys(
                [
                    *_string_list(evidence_set.degraded_reasons_json),
                    *_string_list(evidence_set.rejected_reasons_json),
                ]
            )
        ),
    )
    try:
        with db.begin_nested():
            db.add(binding)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(ResponsePlanEvidenceBinding).where(
                ResponsePlanEvidenceBinding.execution_run_id == execution_run_id,
                ResponsePlanEvidenceBinding.generation_iteration == generation_iteration,
            )
        )
        if existing is None:
            raise
        binding = existing
    return load_authorized_response_plan_binding(
        db,
        response_plan_evidence_binding_id=binding.id,
        project_id=project_id,
        execution_run_id=execution_run_id,
        section_key=plan_section.section_key,
    )


def load_authorized_response_plan_binding(
    db: Session,
    *,
    response_plan_evidence_binding_id: str,
    project_id: str,
    execution_run_id: str,
    section_key: str,
) -> ResponsePlanBindingSnapshot:
    """Rehydrate the persisted plan boundary before draft/review/persist."""
    binding = db.get(ResponsePlanEvidenceBinding, response_plan_evidence_binding_id)
    if binding is None:
        raise ResponsePlanScopeError("response_plan_binding_not_found")
    if binding.execution_run_id != execution_run_id:
        raise ResponsePlanScopeError("response_plan_binding_execution_run_scope_invalid")
    plan_section = db.get(ResponsePlanSection, binding.response_plan_section_id)
    if plan_section is None or plan_section.section_key != section_key:
        raise ResponsePlanScopeError("response_plan_binding_section_scope_invalid")
    response_plan = db.get(ResponsePlan, plan_section.response_plan_id)
    if response_plan is None or response_plan.project_id != project_id:
        raise ResponsePlanScopeError("response_plan_binding_project_scope_invalid")
    run = db.get(ExecutionRun, binding.execution_run_id)
    evidence_set = db.get(EvidenceSet, binding.evidence_set_id)
    if run is None or run.project_id != project_id:
        raise ResponsePlanScopeError("response_plan_binding_run_not_authorized")
    if (
        evidence_set is None
        or evidence_set.project_id != project_id
        or evidence_set.execution_run_id != execution_run_id
        or evidence_set.section_key != section_key
    ):
        raise ResponsePlanScopeError("response_plan_binding_evidence_scope_invalid")
    content_plan = _json_copy(binding.content_plan_json)
    section_snapshot = _plan_section_snapshot(
        db,
        response_plan=response_plan,
        deliverable_section_id=plan_section.deliverable_section_id,
    )
    return ResponsePlanBindingSnapshot(
        response_plan_id=response_plan.id,
        response_plan_version=response_plan.version_number,
        response_plan_section_id=plan_section.id,
        deliverable_section_id=plan_section.deliverable_section_id,
        response_plan_evidence_binding_id=binding.id,
        section_key=plan_section.section_key,
        evidence_set_id=binding.evidence_set_id,
        execution_run_id=binding.execution_run_id,
        generation_iteration=binding.generation_iteration,
        evidence_set_status=binding.evidence_set_status,
        unmet_requirement_ids=_string_list(binding.unmet_requirement_ids_json),
        degraded_reasons=_string_list(binding.degraded_reasons_json),
        content_plan=content_plan,
        requirements=section_snapshot.requirements,
    )


def list_response_plans(db: Session, *, project_id: str) -> list[ResponsePlan]:
    return list(
        db.scalars(
            select(ResponsePlan)
            .where(ResponsePlan.project_id == project_id)
            .order_by(ResponsePlan.version_number.desc(), ResponsePlan.created_at.desc())
        ).all()
    )


def get_response_plan(
    db: Session,
    *,
    response_plan_id: str,
    project_id: str,
) -> ResponsePlan | None:
    return db.scalar(
        select(ResponsePlan).where(
            ResponsePlan.id == response_plan_id,
            ResponsePlan.project_id == project_id,
        )
    )


__all__ = [
    "ResponsePlanBindingSnapshot",
    "ResponsePlanScopeError",
    "ResponsePlanSectionSnapshot",
    "capture_response_plan_binding",
    "ensure_response_plan_section",
    "get_response_plan",
    "list_response_plans",
    "load_authorized_response_plan_binding",
]
