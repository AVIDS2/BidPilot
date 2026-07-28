from __future__ import annotations

from uuid import uuid4

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
)
from contracts.response_plans import (
    capture_response_plan_binding,
    ensure_response_plan_section,
)


def _create_project(client, name: str) -> str:
    response = client.post(
        "/projects",
        json={"name": name, "scenario_package": "bidpilot"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_response_plan(project_id: str) -> tuple[str, str, str, str]:
    db = SessionLocal()
    try:
        section = db.scalar(
            select(DeliverableSection)
            .join(Deliverable, Deliverable.id == DeliverableSection.deliverable_id)
            .where(
                Deliverable.project_id == project_id,
                DeliverableSection.section_key == "technical-approach",
            )
            .order_by(Deliverable.id.asc(), DeliverableSection.sort_order.asc())
            .limit(1)
        )
        if section is None:
            deliverable = Deliverable(
                id=str(uuid4()),
                project_id=project_id,
                type="proposal",
                title="API response plan fixture",
                status="draft",
            )
            db.add(deliverable)
            db.flush()
            section = DeliverableSection(
                id=str(uuid4()),
                deliverable_id=deliverable.id,
                section_key="technical-approach",
                title="技术方案",
                status="draft",
                assignee_type="ai",
                sort_order=1,
            )
            db.add(section)
            db.flush()
        requirement = RequirementItem(
            id=str(uuid4()),
            project_id=project_id,
            section_key=section.section_key,
            requirement_text="须提供可验证的部署和验收方案。",
            priority="high",
            status="open",
            verification_status="unverified",
        )
        run = ExecutionRun(
            id=str(uuid4()),
            project_id=project_id,
            run_type="draft_section",
            status="running",
        )
        db.add_all((requirement, run))
        db.flush()
        evidence_set = EvidenceSet(
            id=str(uuid4()),
            project_id=project_id,
            execution_run_id=run.id,
            section_key=section.section_key,
            query_text="部署验收",
            status="missing_evidence",
            degraded_reasons_json=[],
            rejected_reasons_json=[],
            unmet_requirement_ids_json=[requirement.id],
        )
        db.add(evidence_set)
        db.flush()

        plan_section = ensure_response_plan_section(
            db,
            project_id=project_id,
            section_key=section.section_key,
        )
        binding = capture_response_plan_binding(
            db,
            project_id=project_id,
            execution_run_id=run.id,
            evidence_set_id=evidence_set.id,
            response_plan_section_id=plan_section.response_plan_section_id,
            generation_iteration=1,
            content_plan={
                "section_key": section.section_key,
                "outline": ["部署计划", "验收计划"],
                "key_points": [requirement.requirement_text],
            },
        )
        db.commit()
        return (
            plan_section.response_plan_id,
            section.id,
            requirement.id,
            binding.response_plan_evidence_binding_id,
        )
    finally:
        db.close()


def test_response_plan_endpoints_expose_immutable_mapping_snapshot(client) -> None:
    project_id = _create_project(client, "Response Plan API Project")
    response_plan_id, section_id, requirement_id, binding_id = _create_response_plan(project_id)

    listed = client.get("/response-plans", params={"project_id": project_id})
    assert listed.status_code == 200, listed.text
    assert [plan["id"] for plan in listed.json()] == [response_plan_id]
    assert listed.json()[0]["version_number"] == 1
    assert listed.json()[0]["status"] == "active"

    detail = client.get(
        f"/response-plans/{response_plan_id}",
        params={"project_id": project_id},
    )
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["id"] == response_plan_id
    plan_section = next(
        section
        for section in body["sections"]
        if section["deliverable_section_id"] == section_id
    )
    assert plan_section["deliverable_section_id"] == section_id
    assert plan_section["section_key"] == "technical-approach"
    assert plan_section["requirements"][0]["requirement_id"] == requirement_id
    assert plan_section["requirements"][0]["requirement_text"] == "须提供可验证的部署和验收方案。"
    assert plan_section["evidence_bindings"][0]["id"] == binding_id
    assert plan_section["evidence_bindings"][0]["content_plan"]["outline"] == [
        "部署计划",
        "验收计划",
    ]


def test_response_plan_endpoints_hide_other_organization_projects(client) -> None:
    suffix = uuid4().hex[:8]
    db = SessionLocal()
    try:
        organization = Organization(
            id=str(uuid4()),
            slug=f"response-plan-other-{suffix}",
            name="Other Response Plan Organization",
        )
        project = Project(
            id=str(uuid4()),
            org_id=organization.id,
            slug=f"response-plan-other-project-{suffix}",
            name="Other Response Plan Project",
            scenario_package="bidpilot",
        )
        db.add_all((organization, project))
        db.commit()
    finally:
        db.close()

    response = client.get("/response-plans", params={"project_id": project.id})
    assert response.status_code == 404
