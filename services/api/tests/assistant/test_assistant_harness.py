"""Tests for the product-native assistant harness."""

from __future__ import annotations

import json
import uuid

from app.models import Project


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
    response = client.post(
        "/assistant/stream",
        json={"message": "创建一个项目，名字叫 星河投标"},
    )

    assert response.status_code == 200
    events = _events(response.text)
    assert ("assistant.intent_detected", {"mode": "tool_action", "tool_name": "create_project"}) in events

    confirmation_events = [payload for event, payload in events if event == "assistant.confirmation_requested"]
    assert confirmation_events
    assert confirmation_events[0]["tool_name"] == "create_project"
    assert confirmation_events[0]["arguments"]["name"] == "星河投标"
    assert test_db.query(Project).filter(Project.name == "星河投标").first() is None


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
