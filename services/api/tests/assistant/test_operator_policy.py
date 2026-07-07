from __future__ import annotations

import uuid

import pytest

from app.auth.schemas import CurrentUser
from app.models import Project


def test_operator_metadata_marks_delete_project_destructive() -> None:
    from app.agent.policy import get_tool_policy, tool_requires_approval

    policy = get_tool_policy("delete_project")

    assert policy is not None
    assert policy.label_zh == "删除项目"
    assert policy.risk_level == "destructive"
    assert policy.requires_typed_confirmation is True
    assert tool_requires_approval("search_projects", "request_approval") is False
    assert tool_requires_approval("create_project", "request_approval") is True
    assert tool_requires_approval("create_project", "full_access") is False
    assert tool_requires_approval("delete_project", "full_access") is True


def test_tool_confirmation_payload_is_user_facing() -> None:
    from app.agent.streaming import _extract_confirmation_request

    payload = _extract_confirmation_request(
        "delete_project",
        {
            "requires_confirmation": True,
            "requires_typed_confirmation": True,
            "tool_name": "delete_project",
            "arguments": {"project_id": "project-1"},
            "message": "需要输入完整项目名称后再删除。",
            "expected_text": "待删除演示项目",
        },
    )

    assert payload == {
        "tool_name": "delete_project",
        "arguments": {"project_id": "project-1"},
        "message": "需要输入完整项目名称后再删除。",
        "state": "needs_confirmation",
        "requires_typed_confirmation": True,
        "expected_text": "待删除演示项目",
    }


def test_langgraph_agent_exposes_delete_project_tool_without_db_calls() -> None:
    from app.agent.tools import create_tools
    from app.auth.schemas import CurrentUser

    user = CurrentUser(
        id="dev-user",
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id="default",
    )

    tools = create_tools(db=None, user=user)  # type: ignore[arg-type]
    tool_names = {tool.name for tool in tools}

    assert "delete_project" in tool_names


def test_delete_project_tool_summary_is_user_facing() -> None:
    from app.agent.streaming import _extract_summary

    summary = _extract_summary(
        "delete_project",
        {"deleted": True, "project_id": "project-1", "name": "待删除演示项目"},
    )

    assert summary == "项目「待删除演示项目」已删除。"


def test_assistant_audit_redacts_sensitive_arguments_without_masking_section_key() -> None:
    from app.assistant.audit import redact_arguments, redact_text

    redacted = redact_arguments(
        {
            "api_key": "real-secret",
            "section_key": "technical-approach",
            "nested": {"token": "bearer-secret", "name": "公开项目名"},
        }
    )

    assert redacted == {
        "api_key": "***redacted***",
        "section_key": "technical-approach",
        "nested": {"token": "***redacted***", "name": "公开项目名"},
    }

    error = redact_text("provider failed: api_key=sk-live-secret-value Authorization: Bearer abc.def")

    assert "sk-live-secret-value" not in error
    assert "abc.def" not in error
    assert "***redacted***" in error


def test_delete_project_requires_typed_confirmation(
    test_db,
    default_org_id: str,
) -> None:
    from app.assistant.tools import delete_project_tool

    project = Project(
        slug=f"delete-me-{uuid.uuid4().hex[:6]}",
        name="待删除演示项目",
        scenario_package="bidpilot",
        org_id=default_org_id,
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)

    user = CurrentUser(
        id="dev-user",
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=default_org_id,
    )

    with pytest.raises(ValueError, match="项目名称"):
        delete_project_tool(
            test_db,
            user,
            {"project_id": project.id, "confirmation_text": "错误项目名"},
        )
    assert test_db.get(Project, project.id) is not None

    result = delete_project_tool(
        test_db,
        user,
        {"project_id": project.id, "confirmation_text": "待删除演示项目"},
    )

    assert result.tool_name == "delete_project"
    assert result.result["deleted"] is True
    assert test_db.get(Project, project.id) is None
