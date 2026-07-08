"""Tests for the product-native assistant harness."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from app.models import Project


def _ensure_task_state_table() -> None:
    from app.db import engine
    from app.models import AssistantActionAudit, AssistantApproval, ChatTaskState

    ChatTaskState.__table__.create(bind=engine, checkfirst=True)
    AssistantActionAudit.__table__.create(bind=engine, checkfirst=True)
    AssistantApproval.__table__.create(bind=engine, checkfirst=True)


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
    _ensure_task_state_table()
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


def test_create_project_missing_name_can_continue_with_followup(client, test_db, default_user_id: str) -> None:
    _ensure_task_state_table()
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
    _ensure_task_state_table()
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
    _ensure_task_state_table()
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
    _ensure_task_state_table()
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
    _ensure_task_state_table()
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
    _ensure_task_state_table()
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
    _ensure_task_state_table()
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
    _ensure_task_state_table()

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
    _ensure_task_state_table()
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


def test_full_access_allows_low_risk_project_creation_without_confirmation(client, test_db, default_user_id: str) -> None:
    _ensure_task_state_table()
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


def test_stale_provider_config_falls_back_to_official_model(client, default_user_id: str) -> None:
    _ensure_task_state_table()
    response = client.post(
        "/assistant/stream",
        json={
            "message": "打开项目页面",
            "provider_config_id": "deleted-provider-config",
        },
    )

    assert response.status_code == 200
    events = _events(response.text)
    succeeded = [payload for event, payload in events if event == "assistant.tool_succeeded"]
    assert succeeded
    assert succeeded[0]["tool_name"] == "open_page"


def test_assistant_conversation_auto_generates_title(client, test_db, default_user_id: str, monkeypatch) -> None:
    _ensure_task_state_table()
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
    _ensure_task_state_table()
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
