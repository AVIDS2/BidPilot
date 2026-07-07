from __future__ import annotations

import asyncio
import json

from app.auth.schemas import CurrentUser
from app.chat.service import create_conversation
from app.models import AssistantActionAudit, AssistantApproval


def _ensure_assistant_audit_tables() -> None:
    from app.db import engine

    AssistantActionAudit.__table__.create(bind=engine, checkfirst=True)
    AssistantApproval.__table__.create(bind=engine, checkfirst=True)


class FakeAgent:
    def __init__(self, events: list[dict]):
        self.events = events

    async def astream_events(self, *_args, **_kwargs):
        for event in self.events:
            yield event


async def _collect_stream(fake_agent: FakeAgent, conversation_id: str, db, user: CurrentUser) -> list[str]:
    from app.agent.streaming import stream_agent_events

    chunks: list[str] = []
    async for chunk in stream_agent_events(
        fake_agent,
        [],
        {"configurable": {"thread_id": conversation_id}},
        conversation_id,
        db=db,
        user=user,
        approval_mode="risky_only",
    ):
        chunks.append(chunk)
    return chunks


def _events(chunks: list[str]) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for chunk in chunks:
        for part in chunk.strip().split("\n\n"):
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


def test_langgraph_stream_records_tool_success_audit(
    test_db,
    default_user_id: str,
    default_org_id: str,
) -> None:
    _ensure_assistant_audit_tables()
    conversation = create_conversation(test_db, default_user_id, None)
    user = CurrentUser(
        id=default_user_id,
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=default_org_id,
    )
    fake_agent = FakeAgent(
        [
            {
                "event": "on_tool_start",
                "name": "search_projects",
                "run_id": "tool-run-1",
                "data": {"input": {"query": "test"}},
            },
            {
                "event": "on_tool_end",
                "name": "search_projects",
                "run_id": "tool-run-1",
                "data": {"output": json.dumps({"projects": [], "count": 0}, ensure_ascii=False)},
            },
        ]
    )

    chunks = asyncio.run(_collect_stream(fake_agent, conversation.id, test_db, user))
    event_names = [event for event, _payload in _events(chunks)]

    assert "assistant.tool_succeeded" in event_names
    audit = (
        test_db.query(AssistantActionAudit)
        .filter_by(conversation_id=conversation.id, tool_name="search_projects")
        .one()
    )
    assert audit.status == "succeeded"
    assert audit.risk_level == "read"
    assert audit.arguments_json == {"query": "test"}
    assert audit.result_summary == "找到 0 条projects记录。"


def test_langgraph_stream_records_pending_approval(
    test_db,
    default_user_id: str,
    default_org_id: str,
) -> None:
    _ensure_assistant_audit_tables()
    conversation = create_conversation(test_db, default_user_id, None)
    user = CurrentUser(
        id=default_user_id,
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=default_org_id,
    )
    fake_agent = FakeAgent(
        [
            {
                "event": "on_tool_start",
                "name": "create_project",
                "run_id": "tool-run-2",
                "data": {"input": {"name": "流式审批项目", "scenario_package": "bidpilot"}},
            },
            {
                "event": "on_tool_end",
                "name": "create_project",
                "run_id": "tool-run-2",
                "data": {
                    "output": json.dumps(
                        {
                            "requires_confirmation": True,
                            "tool_name": "create_project",
                            "arguments": {"name": "流式审批项目", "scenario_package": "bidpilot"},
                            "message": "需要你确认：我将创建项目「流式审批项目」。",
                        },
                        ensure_ascii=False,
                    )
                },
            },
        ]
    )

    chunks = asyncio.run(_collect_stream(fake_agent, conversation.id, test_db, user))
    confirmation_events = [payload for event, payload in _events(chunks) if event == "assistant.confirmation_requested"]

    assert confirmation_events
    assert confirmation_events[0]["approval_id"]
    assert confirmation_events[0]["conversation_id"] == conversation.id

    audit = (
        test_db.query(AssistantActionAudit)
        .filter_by(conversation_id=conversation.id, tool_name="create_project")
        .one()
    )
    assert audit.status == "pending_approval"
    assert audit.risk_level == "low_risk_write"
    assert audit.arguments_json["name"] == "流式审批项目"

    approval = test_db.get(AssistantApproval, confirmation_events[0]["approval_id"])
    assert approval is not None
    assert approval.status == "pending"
    assert approval.action_audit_id == audit.id


def test_langgraph_stream_records_tool_error_as_failed_audit(
    test_db,
    default_user_id: str,
    default_org_id: str,
) -> None:
    _ensure_assistant_audit_tables()
    conversation = create_conversation(test_db, default_user_id, None)
    user = CurrentUser(
        id=default_user_id,
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=default_org_id,
    )
    fake_agent = FakeAgent(
        [
            {
                "event": "on_tool_start",
                "name": "search_projects",
                "run_id": "tool-run-3",
                "data": {"input": {"query": "test"}},
            },
            {
                "event": "on_tool_end",
                "name": "search_projects",
                "run_id": "tool-run-3",
                "data": {"output": json.dumps({"error": "provider api_key=sk-live-secret-value failed"})},
            },
        ]
    )

    chunks = asyncio.run(_collect_stream(fake_agent, conversation.id, test_db, user))
    succeeded = [payload for event, payload in _events(chunks) if event == "assistant.tool_succeeded"]

    assert succeeded
    assert succeeded[0]["summary"].startswith("操作失败")
    assert "sk-live-secret-value" not in json.dumps(succeeded[0], ensure_ascii=False)
    assert "***redacted***" in json.dumps(succeeded[0], ensure_ascii=False)
    audit = (
        test_db.query(AssistantActionAudit)
        .filter_by(conversation_id=conversation.id, tool_name="search_projects")
        .one()
    )
    assert audit.status == "failed"
    assert "sk-live-secret-value" not in (audit.error_message or "")
    assert "***redacted***" in (audit.error_message or "")


def test_langgraph_stream_redacts_success_summary_in_sse_and_audit(
    test_db,
    default_user_id: str,
    default_org_id: str,
) -> None:
    _ensure_assistant_audit_tables()
    conversation = create_conversation(test_db, default_user_id, None)
    user = CurrentUser(
        id=default_user_id,
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=default_org_id,
    )
    fake_agent = FakeAgent(
        [
            {
                "event": "on_tool_start",
                "name": "create_project",
                "run_id": "tool-run-4",
                "data": {"input": {"name": "api_key=sk-live-secret-value"}},
            },
            {
                "event": "on_tool_end",
                "name": "create_project",
                "run_id": "tool-run-4",
                "data": {
                    "output": json.dumps(
                        {"name": "api_key=sk-live-secret-value", "status": "created"},
                        ensure_ascii=False,
                    )
                },
            },
        ]
    )

    chunks = asyncio.run(_collect_stream(fake_agent, conversation.id, test_db, user))
    succeeded = [payload for event, payload in _events(chunks) if event == "assistant.tool_succeeded"]

    assert succeeded
    assert "sk-live-secret-value" not in succeeded[0]["summary"]
    assert "***redacted***" in succeeded[0]["summary"]
    assert "sk-live-secret-value" not in json.dumps(succeeded[0]["result"], ensure_ascii=False)
    assert "***redacted***" in json.dumps(succeeded[0]["result"], ensure_ascii=False)
    audit = (
        test_db.query(AssistantActionAudit)
        .filter_by(conversation_id=conversation.id, tool_name="create_project")
        .one()
    )
    assert audit.status == "succeeded"
    assert "sk-live-secret-value" not in (audit.result_summary or "")
    assert "***redacted***" in (audit.result_summary or "")
