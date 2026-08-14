from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    Deliverable,
    DeliverableSection,
    EvidenceSet,
    ExecutionRun,
    Organization,
    Project,
    RequirementItem,
    ResponsePlan,
    User,
)
from contracts.response_plans import (
    ResponsePlanScopeError,
    capture_response_plan_binding,
    ensure_response_plan_section,
    load_authorized_response_plan_binding,
)


def _create_response_plan_scope(db, *, suffix: str, name: str) -> tuple[
    Project,
    DeliverableSection,
    RequirementItem,
    ExecutionRun,
    EvidenceSet,
    User,
]:
    organization = Organization(
        id=str(uuid4()),
        slug=f"response-plan-{name}-{suffix}",
        name=f"Response Plan {name}",
    )
    owner = User(
        id=str(uuid4()),
        org_id=organization.id,
        email=f"response-plan-{name}-{suffix}@example.test",
        display_name=f"{name} Owner",
        password_hash="test-only-password-hash",
    )
    project = Project(
        id=str(uuid4()),
        org_id=organization.id,
        slug=f"response-plan-project-{name}-{suffix}",
        name=f"Response Plan Project {name}",
        scenario_package="bidpilot",
    )
    deliverable = Deliverable(
        id=str(uuid4()),
        project_id=project.id,
        type="proposal",
        title=f"Response Plan Deliverable {name}",
        status="draft",
    )
    section = DeliverableSection(
        id=str(uuid4()),
        deliverable_id=deliverable.id,
        section_key="technical-approach",
        title="技术方案",
        status="draft",
        assignee_type="ai",
        sort_order=1,
    )
    requirement = RequirementItem(
        id=str(uuid4()),
        project_id=project.id,
        section_key=section.section_key,
        requirement_text="必须提供可追溯的部署与验收方案。",
        priority="high",
        status="open",
        owner_user_id=owner.id,
        verification_status="unverified",
    )
    run = ExecutionRun(
        id=str(uuid4()),
        project_id=project.id,
        run_type="draft_section",
        status="running",
    )
    evidence_set = EvidenceSet(
        id=str(uuid4()),
        project_id=project.id,
        execution_run_id=run.id,
        section_key=section.section_key,
        query_text="部署与验收方案",
        status="missing_evidence",
        degraded_reasons_json=[],
        rejected_reasons_json=[],
        unmet_requirement_ids_json=[requirement.id],
    )
    db.add(organization)
    db.flush()
    db.add_all((owner, project))
    db.flush()
    db.add(deliverable)
    db.flush()
    db.add_all((section, requirement, run))
    db.flush()
    db.add(evidence_set)
    db.flush()
    return project, section, requirement, run, evidence_set, owner


def test_response_plan_revision_preserves_requirement_owner_snapshot() -> None:
    suffix = uuid4().hex[:8]
    db = SessionLocal()
    try:
        project, section, requirement, run, evidence_set, owner = _create_response_plan_scope(
            db,
            suffix=suffix,
            name="snapshot",
        )
        db.commit()

        first_section = ensure_response_plan_section(
            db,
            project_id=project.id,
            section_key=section.section_key,
        )
        first_binding = capture_response_plan_binding(
            db,
            project_id=project.id,
            execution_run_id=run.id,
            evidence_set_id=evidence_set.id,
            response_plan_section_id=first_section.response_plan_section_id,
            generation_iteration=1,
            content_plan={
                "section_key": section.section_key,
                "outline": ["部署方案", "验收方案"],
                "key_points": [requirement.requirement_text],
            },
        )
        replay = capture_response_plan_binding(
            db,
            project_id=project.id,
            execution_run_id=run.id,
            evidence_set_id=evidence_set.id,
            response_plan_section_id=first_section.response_plan_section_id,
            generation_iteration=1,
            content_plan={"section_key": section.section_key, "outline": ["ignored on replay"]},
        )
        db.commit()

        assert replay.response_plan_evidence_binding_id == first_binding.response_plan_evidence_binding_id
        assert first_binding.response_plan_version == 1
        assert first_binding.requirements == (
            {
                "id": requirement.id,
                "section_key": section.section_key,
                "requirement_text": "必须提供可追溯的部署与验收方案。",
                "priority": "high",
                "owner_user_id": owner.id,
                "verification_status": "unverified",
                "lock_version": 1,
            },
        )

        requirement.requirement_text = "必须提供可追溯的部署、验收和故障演练方案。"
        requirement.priority = "critical"
        db.commit()

        second_section = ensure_response_plan_section(
            db,
            project_id=project.id,
            section_key=section.section_key,
        )
        db.commit()

        assert second_section.response_plan_id != first_section.response_plan_id
        assert second_section.response_plan_version == 2
        assert second_section.requirements[0]["requirement_text"] == (
            "必须提供可追溯的部署、验收和故障演练方案。"
        )
        assert second_section.requirements[0]["lock_version"] == 2

        original_binding = load_authorized_response_plan_binding(
            db,
            response_plan_evidence_binding_id=first_binding.response_plan_evidence_binding_id,
            project_id=project.id,
            execution_run_id=run.id,
            section_key=section.section_key,
        )
        assert original_binding.response_plan_version == 1
        assert original_binding.requirements[0]["requirement_text"] == (
            "必须提供可追溯的部署与验收方案。"
        )
        assert original_binding.requirements[0]["owner_user_id"] == owner.id
        assert original_binding.content_plan["outline"] == ["部署方案", "验收方案"]

        plans = list(
            db.scalars(
                select(ResponsePlan)
                .where(ResponsePlan.project_id == project.id)
                .order_by(ResponsePlan.version_number.asc())
            ).all()
        )
        assert [(plan.version_number, plan.status) for plan in plans] == [
            (1, "superseded"),
            (2, "active"),
        ]
    finally:
        db.rollback()
        db.close()


def test_response_plan_binding_rejects_cross_project_and_cross_run_scope() -> None:
    suffix = uuid4().hex[:8]
    db = SessionLocal()
    try:
        project, section, _, run, evidence_set, _ = _create_response_plan_scope(
            db,
            suffix=suffix,
            name="target",
        )
        foreign_project, _, _, foreign_run, foreign_evidence_set, _ = _create_response_plan_scope(
            db,
            suffix=suffix,
            name="foreign",
        )
        db.commit()
        plan_section = ensure_response_plan_section(
            db,
            project_id=project.id,
            section_key=section.section_key,
        )
        binding = capture_response_plan_binding(
            db,
            project_id=project.id,
            execution_run_id=run.id,
            evidence_set_id=evidence_set.id,
            response_plan_section_id=plan_section.response_plan_section_id,
            generation_iteration=1,
            content_plan={"section_key": section.section_key},
        )
        db.commit()

        with pytest.raises(ResponsePlanScopeError, match="evidence_set_scope_invalid"):
            capture_response_plan_binding(
                db,
                project_id=project.id,
                execution_run_id=run.id,
                evidence_set_id=foreign_evidence_set.id,
                response_plan_section_id=plan_section.response_plan_section_id,
                generation_iteration=2,
                content_plan={"section_key": section.section_key},
            )

        with pytest.raises(ResponsePlanScopeError, match="execution_run_scope_invalid"):
            capture_response_plan_binding(
                db,
                project_id=project.id,
                execution_run_id=foreign_run.id,
                evidence_set_id=evidence_set.id,
                response_plan_section_id=plan_section.response_plan_section_id,
                generation_iteration=2,
                content_plan={"section_key": section.section_key},
            )

        with pytest.raises(ResponsePlanScopeError, match="execution_run_scope_invalid"):
            load_authorized_response_plan_binding(
                db,
                response_plan_evidence_binding_id=binding.response_plan_evidence_binding_id,
                project_id=project.id,
                execution_run_id=foreign_run.id,
                section_key=section.section_key,
            )

        assert foreign_project.id != project.id
    finally:
        db.rollback()
        db.close()


def test_response_plan_requires_exact_section_for_duplicate_section_keys() -> None:
    suffix = uuid4().hex[:8]
    db = SessionLocal()
    try:
        project, first_section, _, _, _, _ = _create_response_plan_scope(
            db,
            suffix=suffix,
            name="duplicate",
        )
        second_deliverable = Deliverable(
            id=str(uuid4()),
            project_id=project.id,
            type="proposal",
            title="Second proposal",
            status="draft",
        )
        second_section = DeliverableSection(
            id=str(uuid4()),
            deliverable_id=second_deliverable.id,
            section_key=first_section.section_key,
            title="Second technical approach",
            status="draft",
            assignee_type="ai",
            sort_order=1,
        )
        db.add_all((second_deliverable, second_section))
        db.commit()

        with pytest.raises(ResponsePlanScopeError, match="response_plan_section_ambiguous"):
            ensure_response_plan_section(
                db,
                project_id=project.id,
                section_key=first_section.section_key,
            )

        exact = ensure_response_plan_section(
            db,
            project_id=project.id,
            section_key=second_section.section_key,
            deliverable_section_id=second_section.id,
        )

        assert exact.deliverable_section_id == second_section.id
        assert exact.deliverable_section_id != first_section.id
    finally:
        db.rollback()
        db.close()
