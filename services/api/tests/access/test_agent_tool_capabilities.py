import json

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.schemas import CurrentUser
from app.db import Base
from app.models import (
    BidRequirementProfile,
    Deliverable,
    DeliverableSection,
    Organization,
    Project,
    ProjectMember,
    RequirementItem,
    SectionVersion,
    User,
)


def _current(user: User) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        plan="professional",
        email_verified=True,
        disabled=False,
        org_id=user.org_id,
        org_slug="acme",
    )


@pytest.fixture()
def agent_db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        org = Organization(id="org-acme", slug="acme", name="Acme")
        other_org = Organization(id="org-other", slug="other", name="Other")
        project = Project(
            id="project-alpha",
            org_id=org.id,
            slug="alpha",
            name="Restricted Bid",
            scenario_package="bidpilot",
        )
        users = {
            role: User(
                id=f"user-{role}",
                org_id=org.id,
                email=f"{role}@acme.test",
                display_name=role.title(),
                password_hash="test-only",
                role="member",
                email_verified=True,
            )
            for role in ("owner", "contributor", "reviewer", "non_member")
        }
        users["outsider"] = User(
            id="user-outsider",
            org_id=other_org.id,
            email="outsider@other.test",
            display_name="Outsider",
            password_hash="test-only",
            role="member",
            email_verified=True,
        )
        deliverable = Deliverable(
            id="deliverable-alpha",
            project_id=project.id,
            type="proposal",
            title="Proposal",
            status="approved",
        )
        session.add_all([org, other_org, project, *users.values(), deliverable])
        session.flush()
        session.add_all(
            [
                ProjectMember(project_id=project.id, user_id=users[role].id, role=role)
                for role in ("owner", "contributor", "reviewer")
            ]
        )
        session.commit()
        yield session, users, project, deliverable
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_harness_tools_only_search_and_read_member_projects(agent_db) -> None:
    from app.assistant.tools import execute_tool

    db, users, project, _deliverable = agent_db
    result = execute_tool(db, _current(users["contributor"]), "search_projects", {"query": "restricted"})
    assert [
        {
            key: item[key]
            for key in ("id", "name", "status", "scenario_package")
        }
        for item in result.result["items"]
    ] == [
        {
            "id": project.id,
            "name": "Restricted Bid",
            "status": "active",
            "scenario_package": "bidpilot",
        }
    ]

    no_projects = execute_tool(db, _current(users["non_member"]), "search_projects", {})
    assert no_projects.result["items"] == []
    assert no_projects.result["count"] == 0

    with pytest.raises(HTTPException) as exc_info:
        execute_tool(
            db,
            _current(users["non_member"]),
            "get_project_summary",
            {"project_id": project.id},
        )
    assert exc_info.value.status_code == 404


def test_harness_tools_do_not_turn_approval_into_permission(agent_db) -> None:
    from app.assistant.tools import execute_tool

    db, users, project, deliverable = agent_db

    with pytest.raises(HTTPException) as draft_error:
        execute_tool(
            db,
            _current(users["reviewer"]),
            "start_draft_section",
            {"project_id": project.id, "section_key": "technical"},
        )
    assert draft_error.value.status_code == 403

    with pytest.raises(HTTPException) as export_error:
        execute_tool(
            db,
            _current(users["contributor"]),
            "export_deliverable",
            {"project_id": project.id, "deliverable_id": deliverable.id, "format": "docx"},
        )
    assert export_error.value.status_code == 403

    with pytest.raises(HTTPException) as delete_error:
        execute_tool(
            db,
            _current(users["contributor"]),
            "delete_project",
            {"project_id": project.id, "confirmation_text": project.name},
        )
    assert delete_error.value.status_code == 403


def test_harness_export_denies_a_cross_org_project(agent_db) -> None:
    from app.assistant.tools import execute_tool

    db, users, project, deliverable = agent_db

    with pytest.raises(HTTPException) as export_error:
        execute_tool(
            db,
            _current(users["outsider"]),
            "export_deliverable",
            {"project_id": project.id, "deliverable_id": deliverable.id, "format": "docx"},
        )

    assert export_error.value.status_code == 404


def test_langgraph_tools_use_the_same_accessible_project_set(agent_db) -> None:
    from app.agent.tools import create_tools

    db, users, project, _deliverable = agent_db
    tools = {tool.name: tool for tool in create_tools(db, _current(users["contributor"]))}
    payload = json.loads(tools["search_projects"].invoke({"query": "restricted"}))

    assert payload["projects"] == [
        {
            "id": project.id,
            "name": "Restricted Bid",
            "status": "active",
            "scenario": "bidpilot",
        }
    ]


def test_readiness_tools_are_project_scoped_and_user_facing(agent_db) -> None:
    from app.assistant.tools import execute_tool
    from app.agent.tools import create_tools

    db, users, project, _deliverable = agent_db
    requirement = RequirementItem(
        id="requirement-alpha",
        project_id=project.id,
        section_key="qualification",
        requirement_text="Provide a current security certification.",
        source_locator_json={"section": "3.2", "text_anchor": "security certification"},
        priority="high",
    )
    requirement.bid_profile = BidRequirementProfile(
        bid_category="qualification",
        is_mandatory=True,
        risk_level="high",
        coverage_status="uncovered",
        evidence_status="missing",
    )
    db.add(requirement)
    db.commit()

    summary = execute_tool(
        db,
        _current(users["contributor"]),
        "get_readiness_summary",
        {"project_id": project.id},
    )
    gaps = execute_tool(
        db,
        _current(users["contributor"]),
        "list_readiness_gaps",
        {"project_id": project.id, "kind": "high_risk"},
    )
    source = execute_tool(
        db,
        _current(users["reviewer"]),
        "open_requirement_source",
        {"requirement_id": requirement.id},
    )

    assert summary.result["readiness_score"] == 0
    assert summary.summary.startswith("项目「Restricted Bid」当前就绪度为")
    assert gaps.result["items"] == [
        {
            "id": requirement.id,
            "requirement_text": requirement.requirement_text,
            "risk_level": "high",
            "coverage_status": "uncovered",
            "evidence_status": "missing",
            "owner_user_id": None,
            "source_locator_json": requirement.source_locator_json,
        }
    ]
    assert source.result["source_locator_json"] == requirement.source_locator_json
    assert "来源定位" in source.summary

    with pytest.raises(HTTPException) as exc_info:
        execute_tool(
            db,
            _current(users["non_member"]),
            "get_readiness_summary",
            {"project_id": project.id},
        )
    assert exc_info.value.status_code == 404

    langgraph_tools = {tool.name: tool for tool in create_tools(db, _current(users["contributor"]))}
    langgraph_summary = json.loads(
        langgraph_tools["get_readiness_summary"].invoke({"project_id": project.id})
    )
    assert langgraph_summary["readiness_score"] == 0


def test_agent_can_generate_governed_export_and_readiness_artifacts(agent_db, monkeypatch) -> None:
    from app.assistant.tools import execute_tool

    db, users, project, deliverable = agent_db
    section = DeliverableSection(
        id="section-export-alpha",
        deliverable_id=deliverable.id,
        section_key="technical",
        title="Technical Response",
        status="approved",
    )
    db.add(section)
    approved_version = SectionVersion(
        deliverable_section_id=section.id,
        version_number=1,
        content_markdown="已审核的技术响应。",
        created_by_actor="user-owner",
    )
    db.add(approved_version)
    db.flush()
    section.approved_version_id = approved_version.id
    db.commit()

    monkeypatch.setattr(
        "app.adapters.storage.upload_bytes",
        lambda project_id, object_name, data, content_type: f"bucket/{object_name}",
    )
    monkeypatch.setattr(
        "app.readiness.service.upload_bytes",
        lambda project_id, object_name, data, content_type: f"bucket/{object_name}",
    )

    export = execute_tool(
        db,
        _current(users["owner"]),
        "export_deliverable",
        {"project_id": project.id, "deliverable_id": deliverable.id, "format": "docx"},
    )
    readiness = execute_tool(
        db,
        _current(users["owner"]),
        "generate_readiness_pack",
        {"project_id": project.id},
    )

    assert export.result["status"] == "ready"
    assert export.result["download_path"] == f"/export/records/{export.result['export_id']}/docx"
    assert export.result["persisted"] is True
    assert readiness.result["status"] == "generated"
    assert readiness.result["xlsx_download_path"].endswith("/xlsx")
    assert readiness.result["docx_download_path"].endswith("/docx")


def test_agent_review_decision_keeps_human_role_and_project_boundary(agent_db) -> None:
    from app.assistant.tools import execute_tool

    db, users, project, deliverable = agent_db
    section = DeliverableSection(
        id="section-review-alpha",
        deliverable_id=deliverable.id,
        section_key="commercial",
        title="Commercial Response",
        status="pending_review",
    )
    db.add(section)
    version = SectionVersion(
        deliverable_section_id=section.id,
        version_number=1,
        content_markdown="待审核的商务响应。",
        created_by_actor="ai",
    )
    db.add(version)
    db.commit()

    result = execute_tool(
        db,
        _current(users["reviewer"]),
        "submit_review_decision",
        {
            "project_id": project.id,
            "section_id": section.id,
            "section_version_id": version.id,
            "decision": "approved",
            "comment": "已核对投标要求。",
        },
    )

    db.refresh(section)
    assert result.result["decision"] == "approved"
    assert result.summary == "章节审核已通过。"
    assert section.status == "approved"
