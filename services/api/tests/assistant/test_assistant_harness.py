"""Tests for the product-native assistant harness."""

from __future__ import annotations

import json
import uuid

from app.models import Project


def _ensure_task_state_table() -> None:
    from app.db import engine
    from app.models import ChatTaskState

    ChatTaskState.__table__.create(bind=engine, checkfirst=True)


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
    assert test_db.query(Project).filter(Project.name == project_name).first() is None


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
