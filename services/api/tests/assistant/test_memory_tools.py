from __future__ import annotations

import json
from uuid import uuid4

from app.auth.schemas import CurrentUser
from app.assistant.runtime import classify_locally
from app.assistant.tools import execute_tool
from app.memory.schemas import (
    MemoryGraphExtractionCreate,
    MemoryGraphExtractionRead,
    MemoryPortfolioProjectRead,
)
from contracts import MemoryContextItem, MemoryKind, MemoryScope


def _events(raw: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in raw.strip().split("\n\n"):
        event_type = ""
        payload = ""
        for line in block.splitlines():
            if line.startswith("event: "):
                event_type = line[7:]
            elif line.startswith("data: "):
                payload = line[6:]
        if event_type and payload:
            events.append((event_type, json.loads(payload)))
    return events


def _current_user() -> CurrentUser:
    return CurrentUser(
        id="assistant-memory-user",
        email="assistant-memory@example.test",
        display_name="Assistant Memory",
        role="admin",
        org_id="assistant-memory-org",
        org_slug="assistant-memory",
    )


def test_memory_intents_route_to_governed_tools() -> None:
    remember = classify_locally("请记住：我偏好先给结论，再列出风险。")
    search = classify_locally("查看这个项目的 Bid Wiki", "project-memory")
    portfolio = classify_locally("哪些项目需要知识审核？")

    assert remember.mode == "tool_action"
    assert remember.tool_name == "propose_memory"
    assert remember.arguments["scope"] == "user_private"
    assert remember.arguments["kind"] == "preference"
    assert "先给结论" in remember.arguments["body_markdown"]
    assert search.mode == "tool_action"
    assert search.tool_name == "search_bid_wiki"
    assert search.arguments == {"project_id": "project-memory", "query": "查看这个项目的 Bid Wiki"}
    assert portfolio.mode == "tool_action"
    assert portfolio.tool_name == "list_knowledge_portfolio"
    assert portfolio.arguments == {}


def test_memory_graph_intent_requires_an_explicit_source_record() -> None:
    memory_id = "11111111-1111-1111-1111-111111111111"

    missing_project = classify_locally("生成实体关系提案")
    missing_source = classify_locally("为当前知识生成实体关系提案", "project-memory")
    routed = classify_locally(
        f"为知识记录 {memory_id} 生成实体关系提案",
        "project-memory",
    )

    assert missing_project.mode == "needs_input"
    assert missing_project.tool_name == "propose_memory_graph"
    assert missing_project.missing_fields == ["project_id"]
    assert missing_source.mode == "needs_input"
    assert missing_source.arguments == {"project_id": "project-memory"}
    assert missing_source.missing_fields == ["memory_record_id"]
    assert routed.mode == "workflow_trigger"
    assert routed.tool_name == "propose_memory_graph"
    assert routed.arguments == {"project_id": "project-memory", "memory_record_id": memory_id}


def test_assistant_can_navigate_to_knowledge_portfolio() -> None:
    intent = classify_locally("打开知识资产页面")
    result = execute_tool(object(), _current_user(), "open_page", intent.arguments)

    assert intent.tool_name == "open_page"
    assert result.result == {"route": "/knowledge"}


def test_search_bid_wiki_formats_a_bounded_user_facing_result(monkeypatch) -> None:
    from app.assistant import tools

    monkeypatch.setattr(
        tools,
        "memory_context_for_agent",
        lambda *_args, **_kwargs: type(
            "Context",
            (),
            {
                "memory_version": "memory-v1",
                "degraded_reasons": ("dense_unavailable",),
                "items": (
                    MemoryContextItem(
                        record_id="memory-1",
                        title="交付偏好",
                        body_markdown="先给结论，再列出风险。",
                        scope=MemoryScope.USER_PRIVATE,
                        kind=MemoryKind.PREFERENCE,
                        owner_user_id="assistant-memory-user",
                        citations=(
                            {
                                "source_type": "human_decision",
                                "source_id": "assistant-memory-user",
                                "label": "用户明确写入",
                            },
                        ),
                    ),
                ),
            },
        )(),
    )

    result = execute_tool(
        object(),
        _current_user(),
        "search_bid_wiki",
        {"query": "写作偏好"},
    )

    assert result.summary == "找到 1 条可用记忆。"
    assert result.result == {
        "memory_version": "memory-v1",
        "items": [
            {
                "id": "memory-1",
                "title": "交付偏好",
                "body_markdown": "先给结论，再列出风险。",
                "scope": "user_private",
                "kind": "preference",
                "citations": [
                    {"source_type": "human_decision", "source_id": "assistant-memory-user", "label": "用户明确写入"}
                ],
            }
        ],
        "degraded_reasons": ["dense_unavailable"],
    }


def test_knowledge_portfolio_stays_aggregate_only(monkeypatch) -> None:
    from app.assistant import tools

    monkeypatch.setattr(
        tools,
        "list_memory_portfolio_query",
        lambda *_args, **_kwargs: [
            MemoryPortfolioProjectRead(
                project_id="project-1",
                project_name="投标项目 A",
                active_shared_count=3,
                proposed_shared_count=None,
                latest_shared_memory_at=None,
                latest_compilation_status="succeeded",
                latest_compilation_at=None,
            )
        ],
    )

    result = execute_tool(object(), _current_user(), "list_knowledge_portfolio", {})

    assert result.summary == "已检查 1 个可访问项目的知识状态。"
    assert result.result == {
        "items": [
            {
                "project_id": "project-1",
                "project_name": "投标项目 A",
                "active_shared_count": 3,
                "proposed_shared_count": None,
                "latest_shared_memory_at": None,
                "latest_compilation_status": "succeeded",
                "latest_compilation_at": None,
            }
        ],
        "count": 1,
    }
    assert "body_markdown" not in str(result.result)
    assert "citations" not in str(result.result)


def test_memory_graph_tool_starts_a_reviewable_workflow_without_raw_proposal(monkeypatch) -> None:
    from app.assistant import tools

    captured: dict[str, object] = {}

    def start_graph(_db, payload, _user):
        captured["payload"] = payload
        return MemoryGraphExtractionRead(
            run_id="execution-run-1",
            runtime_run_id="runtime-run-1",
            project_id=payload.project_id,
            memory_record_id=payload.memory_record_id,
            status="queued",
        )

    monkeypatch.setattr(tools, "start_memory_graph_extraction_command", start_graph)

    result = execute_tool(
        object(),
        _current_user(),
        "propose_memory_graph",
        {
            "project_id": "project-1",
            "memory_record_id": "11111111-1111-1111-1111-111111111111",
            "provider_config_id": "provider-1",
            "reasoning_effort": "high",
        },
    )

    assert result.workflow is True
    assert result.summary == "实体关系提案已启动，完成后会进入项目知识审核队列。"
    assert result.result == {
        "run_id": "execution-run-1",
        "runtime_run_id": "runtime-run-1",
        "status": "queued",
        "reused": False,
    }
    assert "memory_record_id" not in result.result
    assert "project_id" not in result.result
    payload = captured["payload"]
    assert isinstance(payload, MemoryGraphExtractionCreate)
    assert payload.provider_config_id == "provider-1"
    assert payload.reasoning_effort == "high"


def test_langgraph_knowledge_portfolio_tool_stays_aggregate_only(monkeypatch) -> None:
    from app.agent import tools as agent_tools

    monkeypatch.setattr(
        agent_tools,
        "list_memory_portfolio_query",
        lambda *_args, **_kwargs: [
            MemoryPortfolioProjectRead(
                project_id="project-1",
                project_name="投标项目 A",
                active_shared_count=3,
                proposed_shared_count=None,
                latest_shared_memory_at=None,
                latest_compilation_status="succeeded",
                latest_compilation_at=None,
            )
        ],
    )

    tool = next(
        candidate
        for candidate in agent_tools.create_tools(object(), _current_user())
        if candidate.name == "list_knowledge_portfolio"
    )
    payload = json.loads(tool.invoke({}))

    assert payload == {
        "items": [
            {
                "project_id": "project-1",
                "project_name": "投标项目 A",
                "active_shared_count": 3,
                "proposed_shared_count": None,
                "latest_shared_memory_at": None,
                "latest_compilation_status": "succeeded",
                "latest_compilation_at": None,
            }
        ],
        "count": 1,
    }
    assert "body_markdown" not in str(payload)
    assert "citations" not in str(payload)


def test_langgraph_agent_exposes_the_same_governed_memory_tools() -> None:
    from app.agent.tools import create_tools

    tool_names = {tool.name for tool in create_tools(object(), _current_user())}

    assert {
        "search_bid_wiki",
        "list_knowledge_portfolio",
        "propose_memory",
        "propose_memory_graph",
        "forget_memory",
    }.issubset(tool_names)


def test_assistant_remember_preference_requires_confirmation_then_persists(client, test_db, default_user_id: str) -> None:
    preference = f"先给结论，再列出风险。{uuid4().hex[:8]}"
    first = client.post(
        "/assistant/stream",
        json={"message": f"请记住：我偏好{preference}"},
    )

    assert first.status_code == 200, first.text
    first_events = _events(first.text)
    confirmation = [payload for event, payload in first_events if event == "assistant.confirmation_requested"]
    assert confirmation
    assert confirmation[0]["tool_name"] == "propose_memory"
    conversation_id = confirmation[0]["conversation_id"]

    second = client.post(
        "/assistant/stream",
        json={"message": "确认", "conversation_id": conversation_id},
    )

    assert second.status_code == 200, second.text
    succeeded = [payload for event, payload in _events(second.text) if event == "assistant.tool_succeeded"]
    assert succeeded
    assert succeeded[0]["tool_name"] == "propose_memory"

    from app.models import MemoryRecord

    record = (
        test_db.query(MemoryRecord)
        .filter(MemoryRecord.owner_user_id == default_user_id, MemoryRecord.body_markdown.contains(preference))
        .one()
    )
    assert record.scope == "user_private"
    assert record.status == "active"
    assert preference in record.body_markdown
