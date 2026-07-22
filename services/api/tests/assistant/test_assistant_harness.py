"""Tests for the product-native assistant harness."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from app.models import (
    BidRequirementProfile,
    Claim,
    ClaimEvidenceLink,
    Evidence,
    Project,
    RequirementClaimLink,
    RequirementEvidenceLink,
    RequirementItem,
)


def _project_exists(name: str) -> bool:
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        return db.query(Project).filter(Project.name == name).first() is not None
    finally:
        db.close()


def _events(response_text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for part in response_text.strip().split("\n\n"):
        event_type = ""
        data_json = ""
        for line in part.splitlines():
            if line.startswith("event: "):
                event_type = line[7:]
            elif line.startswith("data: "):
                data_json = line[6:]
        if event_type and data_json:
            events.append((event_type, json.loads(data_json)))
    return events


def test_create_project_requires_confirmation(client, test_db, default_user_id: str) -> None:
    project_name = f"星河投标{uuid.uuid4().hex[:6]}"
    response = client.post(
        "/assistant/stream",
        json={"message": f"创建一个项目，名字叫 {project_name}"},
    )

    assert response.status_code == 200
    events = _events(response.text)
    assert ("assistant.intent_detected", {"mode": "tool_action", "tool_name": "create_project"}) in events

    confirmation_events = [payload for event, payload in events if event == "assistant.confirmation_requested"]
    assert confirmation_events
    assert confirmation_events[0]["tool_name"] == "create_project"
    assert confirmation_events[0]["arguments"]["name"] == project_name
    assert confirmation_events[0]["approval_id"]
    assert test_db.query(Project).filter(Project.name == project_name).first() is None

    from app.models import AssistantActionAudit, AssistantApproval

    audit = (
        test_db.query(AssistantActionAudit)
        .filter_by(tool_name="create_project", status="pending_approval")
        .order_by(AssistantActionAudit.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.conversation_id == confirmation_events[0]["conversation_id"]
    assert audit.risk_level == "low_risk_write"
    assert audit.arguments_json["name"] == project_name

    approval = test_db.get(AssistantApproval, confirmation_events[0]["approval_id"])
    assert approval is not None
    assert approval.action_audit_id == audit.id
    assert approval.status == "pending"
    assert approval.payload_json["arguments"]["name"] == project_name


def test_demo_workspace_requires_confirmation_then_uses_governed_tool(client, test_db, default_user_id: str) -> None:
    first = client.post("/assistant/stream", json={"message": "带我体验一下演示工作区"})

    assert first.status_code == 200
    events = _events(first.text)
    confirmation = [payload for event, payload in events if event == "assistant.confirmation_requested"]
    assert confirmation
    assert confirmation[0]["tool_name"] == "create_demo_workspace"
    assert "不会使用 AI 额度" in confirmation[0]["message"]

    conversation_id = [payload for event, payload in events if event == "assistant.start"][0]["conversation_id"]
    approved = client.post(
        "/assistant/stream",
        json={"message": "确认", "conversation_id": conversation_id},
    )

    assert approved.status_code == 200
    approved_events = _events(approved.text)
    succeeded = [payload for event, payload in approved_events if event == "assistant.tool_succeeded"]
    assert succeeded
    assert succeeded[0]["tool_name"] == "create_demo_workspace"
    assert succeeded[0]["result"]["id"]


def test_create_project_missing_name_can_continue_with_followup(client, test_db, default_user_id: str) -> None:
    first_response = client.post(
        "/assistant/stream",
        json={"message": "创建一个新项目"},
    )
    assert first_response.status_code == 200
    first_events = _events(first_response.text)
    start_events = [payload for event, payload in first_events if event == "assistant.start"]
    assert start_events
    conversation_id = start_events[0]["conversation_id"]

    second_response = client.post(
        "/assistant/stream",
        json={
            "message": "你来",
            "conversation_id": conversation_id,
        },
    )

    assert second_response.status_code == 200
    second_events = _events(second_response.text)
    confirmation_events = [payload for event, payload in second_events if event == "assistant.confirmation_requested"]
    assert confirmation_events
    assert confirmation_events[0]["tool_name"] == "create_project"
    assert confirmation_events[0]["arguments"]["name"].startswith("新建投标项目")


def test_create_project_missing_name_accepts_named_followup(client, test_db, default_user_id: str) -> None:
    first_response = client.post(
        "/assistant/stream",
        json={"message": "创建一个新项目"},
    )
    assert first_response.status_code == 200
    first_events = _events(first_response.text)
    conversation_id = [payload for event, payload in first_events if event == "assistant.start"][0]["conversation_id"]

    second_response = client.post(
        "/assistant/stream",
        json={
            "message": "星河投标",
            "conversation_id": conversation_id,
        },
    )

    assert second_response.status_code == 200
    second_events = _events(second_response.text)
    confirmation_events = [payload for event, payload in second_events if event == "assistant.confirmation_requested"]
    assert confirmation_events
    assert confirmation_events[0]["arguments"]["name"] == "星河投标"


def test_create_project_can_be_confirmed_by_text_followup(client, test_db, default_user_id: str) -> None:
    project_name = f"Text Confirm Project {uuid.uuid4().hex[:6]}"
    first_response = client.post(
        "/assistant/stream",
        json={"message": f"创建项目，名字叫 {project_name}"},
    )
    assert first_response.status_code == 200
    first_events = _events(first_response.text)
    conversation_id = [payload for event, payload in first_events if event == "assistant.start"][0]["conversation_id"]
    assert [payload for event, payload in first_events if event == "assistant.confirmation_requested"]

    second_response = client.post(
        "/assistant/stream",
        json={
            "message": "确认",
            "conversation_id": conversation_id,
        },
    )

    assert second_response.status_code == 200
    second_events = _events(second_response.text)
    event_names = [event for event, _payload in second_events]
    assert "assistant.tool_started" in event_names
    assert "assistant.tool_succeeded" in event_names
    assert _project_exists(project_name)


def test_pending_confirmation_can_be_cancelled_by_text_followup(client, test_db, default_user_id: str) -> None:
    project_name = f"Cancelled Project {uuid.uuid4().hex[:6]}"
    first_response = client.post(
        "/assistant/stream",
        json={"message": f"创建项目，名字叫 {project_name}"},
    )
    assert first_response.status_code == 200
    first_events = _events(first_response.text)
    conversation_id = [payload for event, payload in first_events if event == "assistant.start"][0]["conversation_id"]

    second_response = client.post(
        "/assistant/stream",
        json={
            "message": "取消",
            "conversation_id": conversation_id,
        },
    )

    assert second_response.status_code == 200
    second_events = _events(second_response.text)
    messages = [payload["content"] for event, payload in second_events if event == "assistant.message"]
    assert messages == ["已取消这次操作。"]
    assert test_db.query(Project).filter(Project.name == project_name).first() is None

    from app.models import AssistantActionAudit, AssistantApproval

    audit = (
        test_db.query(AssistantActionAudit)
        .filter_by(tool_name="create_project")
        .order_by(AssistantActionAudit.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.status == "cancelled"
    assert audit.completed_at is not None

    approval = (
        test_db.query(AssistantApproval)
        .filter_by(action_audit_id=audit.id)
        .order_by(AssistantApproval.created_at.desc())
        .first()
    )
    assert approval is not None
    assert approval.status == "cancelled"
    assert approval.resolved_at is not None


def test_expired_pending_confirmation_does_not_execute(client, test_db, default_user_id: str) -> None:
    project_name = f"Expired Approval Project {uuid.uuid4().hex[:6]}"
    first_response = client.post(
        "/assistant/stream",
        json={"message": f"创建项目，名字叫 {project_name}"},
    )
    assert first_response.status_code == 200
    first_events = _events(first_response.text)
    conversation_id = [payload for event, payload in first_events if event == "assistant.start"][0]["conversation_id"]
    confirmation = [payload for event, payload in first_events if event == "assistant.confirmation_requested"][0]

    from app.models import AssistantActionAudit, AssistantApproval

    approval = test_db.get(AssistantApproval, confirmation["approval_id"])
    assert approval is not None
    approval.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)
    test_db.commit()

    second_response = client.post(
        "/assistant/stream",
        json={
            "message": "确认",
            "conversation_id": conversation_id,
        },
    )

    assert second_response.status_code == 200
    second_events = _events(second_response.text)
    failed = [payload for event, payload in second_events if event == "assistant.tool_failed"]
    assert failed
    assert "审批已过期" in failed[0]["error_message"]
    assert test_db.query(Project).filter(Project.name == project_name).first() is None

    test_db.refresh(approval)
    assert approval.status == "expired"
    audit = test_db.get(AssistantActionAudit, approval.action_audit_id)
    assert audit is not None
    assert audit.status == "expired"
    assert audit.completed_at is not None


def test_confirmed_create_project_executes_tool(client, test_db, default_user_id: str) -> None:
    project_name = f"Agent Project {uuid.uuid4().hex[:6]}"

    response = client.post(
        "/assistant/stream",
        json={
            "message": "确认创建项目",
            "confirmation": {
                "approved": True,
                "tool_name": "create_project",
                "arguments": {
                    "name": project_name,
                    "scenario_package": "bidpilot",
                },
            },
        },
    )

    assert response.status_code == 200
    events = _events(response.text)
    event_names = [event for event, _payload in events]
    assert "assistant.tool_started" in event_names
    assert "assistant.tool_succeeded" in event_names

    project = test_db.query(Project).filter(Project.name == project_name).first()
    assert project is not None
    assert project.scenario_package == "bidpilot"

    from app.models import AssistantActionAudit

    audit = (
        test_db.query(AssistantActionAudit)
        .filter_by(tool_name="create_project", status="succeeded")
        .order_by(AssistantActionAudit.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.arguments_json["name"] == project_name
    assert audit.result_summary == f"项目「{project_name}」已创建。"
    assert audit.completed_at is not None


def test_failed_confirmed_tool_records_failed_audit(
    client,
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    project = Project(
        slug=f"failed-delete-{uuid.uuid4().hex[:6]}",
        name="失败删除审计项目",
        scenario_package="bidpilot",
        org_id=default_org_id,
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)

    response = client.post(
        "/assistant/stream",
        json={
            "message": "确认删除项目",
            "confirmation": {
                "approved": True,
                "tool_name": "delete_project",
                "arguments": {
                    "project_id": project.id,
                    "confirmation_text": "错误名称",
                },
            },
        },
    )

    assert response.status_code == 200
    events = _events(response.text)
    failed = [payload for event, payload in events if event == "assistant.tool_failed"]
    assert failed
    assert "完整项目名称" in failed[0]["error_message"]
    assert test_db.get(Project, project.id) is not None

    from app.models import AssistantActionAudit

    audit = (
        test_db.query(AssistantActionAudit)
        .filter_by(tool_name="delete_project", status="failed")
        .order_by(AssistantActionAudit.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.risk_level == "destructive"
    assert audit.arguments_json["confirmation_text"] == "错误名称"
    assert "完整项目名称" in (audit.error_message or "")


def test_tool_failure_redacts_sse_and_saved_message(
    client,
    test_db,
    default_user_id: str,
    monkeypatch,
) -> None:

    def fail_with_secret(*_args, **_kwargs):
        raise ValueError("provider failed api_key=sk-live-secret-value")

    monkeypatch.setattr("app.assistant.service.execute_tool", fail_with_secret)

    response = client.post(
        "/assistant/stream",
        json={"message": "打开项目页面"},
    )

    assert response.status_code == 200
    assert "sk-live-secret-value" not in response.text
    assert "***redacted***" in response.text

    events = _events(response.text)
    conversation_id = [payload for event, payload in events if event == "assistant.start"][0]["conversation_id"]
    failed = [payload for event, payload in events if event == "assistant.tool_failed"]
    assert failed
    assert "sk-live-secret-value" not in failed[0]["error_message"]

    from app.chat.service import get_conversation_messages

    messages = get_conversation_messages(test_db, conversation_id)
    assistant_messages = [message.content for message in messages if message.role == "assistant"]
    assert assistant_messages
    assert "sk-live-secret-value" not in assistant_messages[-1]

    from app.models import AssistantActionAudit

    audit = (
        test_db.query(AssistantActionAudit)
        .filter_by(conversation_id=conversation_id, tool_name="open_page", status="failed")
        .one()
    )
    assert "sk-live-secret-value" not in (audit.error_message or "")
    assert "***redacted***" in (audit.error_message or "")


def test_open_page_executes_without_confirmation(client, default_user_id: str) -> None:
    response = client.post(
        "/assistant/stream",
        json={"message": "打开项目页面"},
    )

    assert response.status_code == 200
    events = _events(response.text)
    assert not [payload for event, payload in events if event == "assistant.confirmation_requested"]

    succeeded = [payload for event, payload in events if event == "assistant.tool_succeeded"]
    assert succeeded
    assert succeeded[0]["tool_name"] == "open_page"
    assert succeeded[0]["result"]["route"] == "/projects"


def test_readiness_intent_requires_project_context_and_routes_safely() -> None:
    from app.assistant.runtime import classify_locally

    missing = classify_locally("查看这个项目的就绪度")
    routed = classify_locally("列出当前项目的高风险缺口", "project-alpha")

    assert missing.mode == "needs_input"
    assert missing.tool_name == "get_readiness_summary"
    assert missing.missing_fields == ["project_id"]
    assert routed.mode == "tool_action"
    assert routed.tool_name == "list_readiness_gaps"
    assert routed.arguments == {"project_id": "project-alpha", "kind": "high_risk"}


def test_claim_review_queue_intent_requires_project_context_and_routes_safely() -> None:
    from app.assistant.runtime import classify_locally

    missing = classify_locally("查看待核验主张")
    routed = classify_locally("列出当前项目待核验的 AI 主张", "project-alpha")

    assert missing.mode == "needs_input"
    assert missing.tool_name == "list_claim_review_queue"
    assert missing.missing_fields == ["project_id"]
    assert routed.mode == "tool_action"
    assert routed.tool_name == "list_claim_review_queue"
    assert routed.arguments == {"project_id": "project-alpha"}


def test_readiness_pack_intent_routes_to_a_governed_project_action() -> None:
    from app.assistant.runtime import classify_locally

    missing = classify_locally("生成投标准备度包")
    routed = classify_locally("导出当前项目的准备度包", "project-alpha")

    assert missing.mode == "needs_input"
    assert missing.tool_name == "generate_readiness_pack"
    assert missing.missing_fields == ["project_id"]
    assert routed.mode == "tool_action"
    assert routed.tool_name == "generate_readiness_pack"
    assert routed.arguments == {"project_id": "project-alpha"}


def test_review_decision_intent_requires_section_then_routes_with_project_context() -> None:
    from app.assistant.runtime import classify_locally

    section_id = "11111111-1111-1111-1111-111111111111"
    missing = classify_locally("审核通过这个章节", "project-alpha")
    routed = classify_locally(f"审核通过章节 {section_id}", "project-alpha")

    assert missing.mode == "needs_input"
    assert missing.tool_name == "submit_review_decision"
    assert missing.missing_fields == ["section_id"]
    assert routed.mode == "tool_action"
    assert routed.tool_name == "submit_review_decision"
    assert routed.arguments == {
        "project_id": "project-alpha",
        "section_id": section_id,
        "decision": "approved",
    }


def test_readiness_summary_streams_as_a_safe_read(
    client,
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    project = Project(
        slug=f"assistant-readiness-{uuid.uuid4().hex[:6]}",
        name="Assistant Readiness Project",
        scenario_package="bidpilot",
        org_id=default_org_id,
    )
    test_db.add(project)
    test_db.flush()
    requirement = RequirementItem(
        project_id=project.id,
        section_key="qualification",
        requirement_text="Provide the required security certification.",
        priority="high",
    )
    requirement.bid_profile = BidRequirementProfile(
        bid_category="qualification",
        is_mandatory=True,
        risk_level="high",
        coverage_status="uncovered",
        evidence_status="missing",
    )
    test_db.add(requirement)
    test_db.commit()
    test_db.refresh(project)

    response = client.post(
        "/assistant/stream",
        json={
            "message": "查看这个项目的就绪度",
            "project_id": project.id,
        },
    )

    assert response.status_code == 200
    events = _events(response.text)
    assert ("assistant.intent_detected", {"mode": "tool_action", "tool_name": "get_readiness_summary"}) in events
    assert not [payload for event, payload in events if event == "assistant.confirmation_requested"]
    succeeded = [payload for event, payload in events if event == "assistant.tool_succeeded"]
    assert succeeded[0]["tool_name"] == "get_readiness_summary"
    assert succeeded[0]["result"]["readiness_score"] == 0
    assert [event for event, _payload in events].index("assistant.tool_succeeded") < [
        event for event, _payload in events
    ].index("assistant.message")
    messages = [payload["content"] for event, payload in events if event == "assistant.message"]
    assert messages == ["项目「Assistant Readiness Project」当前就绪度为 0.0 分，有 1 个强制项缺口和 1 个证据缺口。"]


def test_claim_review_queue_streams_only_safe_progress_counts(
    client,
    test_db,
    default_org_id: str,
) -> None:
    project = Project(
        slug=f"assistant-claims-{uuid.uuid4().hex[:6]}",
        name="Assistant Claim Review Project",
        scenario_package="bidpilot",
        org_id=default_org_id,
    )
    test_db.add(project)
    test_db.flush()

    ready_requirement = RequirementItem(
        project_id=project.id,
        section_key="qualification",
        requirement_text="Ready requirement",
    )
    blocked_requirement_one = RequirementItem(
        project_id=project.id,
        section_key="technical",
        requirement_text="Blocked requirement one",
    )
    blocked_requirement_two = RequirementItem(
        project_id=project.id,
        section_key="technical",
        requirement_text="Blocked requirement two",
    )
    test_db.add_all([ready_requirement, blocked_requirement_one, blocked_requirement_two])
    test_db.flush()

    ready_evidence = Evidence(project_id=project.id, quote_text="Ready evidence")
    blocked_evidence = Evidence(project_id=project.id, quote_text="Blocked evidence")
    test_db.add_all([ready_evidence, blocked_evidence])
    test_db.flush()

    secret_claim_text = "Internal draft claim must never reach Assistant SSE output."
    ready_claim = Claim(
        project_id=project.id,
        claim_text=secret_claim_text,
        claim_type="factual",
        created_by_actor="ai",
    )
    blocked_claim = Claim(
        project_id=project.id,
        claim_text="Another internal draft claim.",
        claim_type="factual",
        created_by_actor="ai",
    )
    test_db.add_all([ready_claim, blocked_claim])
    test_db.flush()
    test_db.add_all(
        [
            RequirementClaimLink(requirement_id=ready_requirement.id, claim_id=ready_claim.id),
            ClaimEvidenceLink(claim_id=ready_claim.id, evidence_id=ready_evidence.id),
            RequirementEvidenceLink(
                requirement_id=ready_requirement.id,
                evidence_id=ready_evidence.id,
                relation_type="supports",
                verification_status="verified",
            ),
            RequirementClaimLink(requirement_id=blocked_requirement_one.id, claim_id=blocked_claim.id),
            RequirementClaimLink(requirement_id=blocked_requirement_two.id, claim_id=blocked_claim.id),
            ClaimEvidenceLink(claim_id=blocked_claim.id, evidence_id=blocked_evidence.id),
            RequirementEvidenceLink(
                requirement_id=blocked_requirement_one.id,
                evidence_id=blocked_evidence.id,
                relation_type="supports",
                verification_status="verified",
            ),
            RequirementEvidenceLink(
                requirement_id=blocked_requirement_two.id,
                evidence_id=blocked_evidence.id,
                relation_type="supports",
                verification_status="unverified",
            ),
        ]
    )
    test_db.commit()

    response = client.post(
        "/assistant/stream",
        json={
            "message": "查看当前项目的待核验主张",
            "project_id": project.id,
        },
    )

    assert response.status_code == 200
    events = _events(response.text)
    assert ("assistant.intent_detected", {"mode": "tool_action", "tool_name": "list_claim_review_queue"}) in events
    succeeded = [payload for event, payload in events if event == "assistant.tool_succeeded"]
    assert succeeded[0]["tool_name"] == "list_claim_review_queue"
    assert succeeded[0]["result"] == {
        "project_id": project.id,
        "count": 2,
        "ready_to_verify_count": 1,
        "blocked_by_evidence_count": 1,
        "truncated": False,
    }
    assert secret_claim_text not in response.text


def test_full_access_allows_low_risk_project_creation_without_confirmation(client, test_db, default_user_id: str) -> None:
    project_name = f"Full Access Project {uuid.uuid4().hex[:6]}"

    response = client.post(
        "/assistant/stream",
        json={
            "message": f"创建一个项目，名字叫 {project_name}",
            "approval_mode": "full_access",
        },
    )

    assert response.status_code == 200
    events = _events(response.text)
    assert not [payload for event, payload in events if event == "assistant.confirmation_requested"]
    assert [payload for event, payload in events if event == "assistant.tool_succeeded"]
    assert test_db.query(Project).filter(Project.name == project_name).first() is not None


def test_deleted_provider_config_never_falls_back_to_official_model(client, default_user_id: str) -> None:
    response = client.post(
        "/assistant/stream",
        json={
            "message": "打开项目页面",
            "provider_config_id": "deleted-provider-config",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Provider config not found"


def test_inactive_provider_config_never_falls_back_to_official_model(
    client,
    test_db,
    default_user_id: str,
) -> None:
    from app.models import ProviderConfig

    config = ProviderConfig(
        user_id=default_user_id,
        provider_type="openai",
        api_key="unused-inactive-key",
        model="test-model",
        label="Inactive provider",
        is_active=False,
    )
    test_db.add(config)
    test_db.commit()

    response = client.post(
        "/assistant/stream",
        json={
            "message": "打开项目页面",
            "provider_config_id": config.id,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Provider config not found"


def test_assistant_conversation_auto_generates_title(client, test_db, default_user_id: str, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.chat.service._generate_conversation_title",
        lambda *_args, **_kwargs: "平台状态概览",
    )

    response = client.post(
        "/assistant/stream",
        json={"message": "给我一个平台状态和最近活动的概览"},
    )

    assert response.status_code == 200
    events = _events(response.text)
    conversation_id = [payload for event, payload in events if event == "assistant.start"][0]["conversation_id"]

    from app.chat.service import get_conversation

    conversation = get_conversation(test_db, conversation_id, default_user_id)
    assert conversation is not None
    assert conversation.title == "平台状态概览"


def test_start_draft_section_requires_confirmation(client, test_db, default_org_id: str, default_user_id: str) -> None:
    project = Project(
        slug=f"assistant-draft-{uuid.uuid4().hex[:6]}",
        name="Assistant Draft Project",
        scenario_package="bidpilot",
        org_id=default_org_id,
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)

    response = client.post(
        "/assistant/stream",
        json={
            "message": "帮我起草技术方案章节",
            "project_id": project.id,
        },
    )

    assert response.status_code == 200
    events = _events(response.text)
    confirmation_events = [payload for event, payload in events if event == "assistant.confirmation_requested"]
    assert confirmation_events
    assert confirmation_events[0]["tool_name"] == "start_draft_section"
    assert confirmation_events[0]["arguments"]["project_id"] == project.id
    assert confirmation_events[0]["arguments"]["section_key"] == "technical-approach"
