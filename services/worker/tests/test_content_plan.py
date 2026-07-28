"""Unit tests for the deterministic content-plan node."""

from uuid import uuid4

from app.db import SessionLocal
from app.graph.nodes.content_plan import build_content_plan, content_plan_node
from app.models import (
    Deliverable,
    DeliverableSection,
    EvidenceSet,
    ExecutionRun,
    Organization,
    Project,
    RequirementItem,
    ResponsePlanEvidenceBinding,
)


def test_build_content_plan_picks_evidence_and_key_points() -> None:
    plan = build_content_plan(
        section_key="technical-approach",
        evidence_chunks=[
            {
                "chunk_id": "c1",
                "content": "智慧社区综合管理平台采用微服务架构，支持门禁、停车与安防统一接入。",
            },
            {
                "chunk_id": "c2",
                "content": "系统架构图展示三层部署拓扑，并支持国产数据库与中间件。",
            },
        ],
        requirements=[{"requirement_text": "须支持信创环境部署。"}],
    )
    assert plan["section_key"] == "technical-approach"
    assert plan["evidence_picks"]
    assert any("信创" in point for point in plan["key_points"])
    assert plan["figures"]  # architecture cue
    assert plan["tables"]
    assert not plan["gaps"]


def test_content_plan_node_clears_stale_draft_on_replan() -> None:
    result = content_plan_node(
        {
            "section_key": "technical-approach",
            "evidence_chunks": [
                {"chunk_id": "c1", "content": "一期完成基础平台与门禁联动。"}
            ],
            "requirements": [],
            "draft_created": True,
            "draft_markdown": "old draft",
            "review_result": {"passed": False, "issues": ["too short"], "suggestions": [], "overall_score": 0.2},
            "review_passed": False,
            "human_decision": "rejected_with_feedback",
        }
    )
    assert result["content_plan_ready"] is True
    assert result["draft_created"] is False
    assert result["draft_markdown"] == ""
    assert result["review_result"] is None
    assert result["human_decision"] is None
    assert result["content_plan"]["key_points"]


def test_content_plan_node_persists_durable_requirement_and_evidence_binding() -> None:
    suffix = uuid4().hex[:8]
    db = SessionLocal()
    try:
        organization = Organization(
            id=str(uuid4()),
            slug=f"content-plan-{suffix}",
            name="Content Plan Test",
        )
        db.add(organization)
        db.flush()
        project = Project(
            id=str(uuid4()),
            org_id=organization.id,
            slug=f"content-plan-project-{suffix}",
            name="Content Plan Project",
            scenario_package="bidpilot",
        )
        db.add(project)
        db.flush()
        deliverable = Deliverable(
            id=str(uuid4()),
            project_id=project.id,
            type="proposal",
            title="Content Plan Deliverable",
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
        requirement = RequirementItem(
            id=str(uuid4()),
            project_id=project.id,
            section_key=section.section_key,
            requirement_text="必须明确验收标准与部署边界。",
            priority="high",
            status="open",
            verification_status="unverified",
        )
        run = ExecutionRun(
            id=str(uuid4()),
            project_id=project.id,
            run_type="draft_section",
            status="running",
        )
        db.add_all((section, requirement, run))
        db.flush()
        evidence_set = EvidenceSet(
            id=str(uuid4()),
            project_id=project.id,
            execution_run_id=run.id,
            section_key=section.section_key,
            query_text="验收标准",
            status="missing_evidence",
            degraded_reasons_json=[],
            rejected_reasons_json=[],
            unmet_requirement_ids_json=[requirement.id],
        )
        db.add(evidence_set)
        db.commit()

        result = content_plan_node(
            {
                "project_id": project.id,
                "section_key": section.section_key,
                "run_id": run.id,
                "evidence_set_id": evidence_set.id,
                "evidence_chunks": [],
                "requirements": [
                    {"requirement_text": "Untrusted graph-state requirement"}
                ],
                "iteration": 0,
            }
        )

        assert result["content_plan_ready"] is True
        assert result["response_plan_version"] == 1
        assert "必须明确验收标准与部署边界。" in result["content_plan"]["key_points"]
        assert "Untrusted graph-state requirement" not in result["content_plan"]["key_points"]

        binding = db.get(
            ResponsePlanEvidenceBinding,
            result["response_plan_evidence_binding_id"],
        )
        assert binding is not None
        assert binding.evidence_set_id == evidence_set.id
        assert binding.execution_run_id == run.id
        assert binding.generation_iteration == 1
        assert binding.content_plan_json == result["content_plan"]
    finally:
        db.rollback()
        db.close()
