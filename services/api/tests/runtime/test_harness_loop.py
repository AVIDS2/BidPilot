"""Unit tests for the streaming harness helpers and multi-step loop."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.runtime.harness_loop import (
    HARNESS_CAMPAIGN_MAX_STEPS,
    HARNESS_MAX_STEPS,
    StreamingHarness,
    build_capability_tool_specs,
    build_turn_summary,
    resolve_harness_budgets,
)


class _FakeAIMessage:
    def __init__(self, content: str = "", tool_calls: list[dict[str, Any]] | None = None) -> None:
        self.content = content
        self.tool_calls = tool_calls or []


class _FakeBoundLLM:
    def __init__(self, responses: list[_FakeAIMessage]) -> None:
        self.responses = list(responses)
        self.calls: list[list[Any]] = []

    def bind_tools(self, tools: list[Any]) -> "_FakeBoundLLM":
        self.tools = tools
        return self

    def invoke(self, messages: list[Any]) -> _FakeAIMessage:
        self.calls.append(messages)
        if not self.responses:
            return _FakeAIMessage(content="done")
        return self.responses.pop(0)


class _FakeRun:
    def __init__(self) -> None:
        self.id = "run-1"
        self.project_id = None
        self.provider_config_id = None
        self.model = "test-model"


class _FakeUser:
    id = "user-1"
    org_id = "org-1"
    email = "dev@docpilot.local"
    display_name = "Dev"
    role = "admin"


def test_build_capability_tool_specs_covers_registry() -> None:
    tools = build_capability_tool_specs()
    names = {tool["function"]["name"] for tool in tools}
    assert "search_projects" in names
    assert "create_project" in names
    assert "list_requirements" in names
    assert "run_section_campaign" in names
    assert all(tool["type"] == "function" for tool in tools)


def test_build_turn_summary_is_rule_based() -> None:
    summary = build_turn_summary(["search_projects", "search_projects", "list_requirements"])
    assert "搜索项目" in summary
    assert "×2" in summary
    assert "查看需求" in summary


def test_resolve_harness_budgets_raises_for_campaign_language() -> None:
    default_steps, default_tools = resolve_harness_budgets("搜索项目")
    campaign_steps, campaign_tools = resolve_harness_budgets("请把全部章节批量起草")
    assert default_steps == HARNESS_MAX_STEPS
    assert campaign_steps == HARNESS_CAMPAIGN_MAX_STEPS
    assert campaign_tools >= default_tools


def test_streaming_harness_answers_without_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from app.runtime import harness_loop as module
    from app.usage.schemas import ProviderSource

    llm = _FakeBoundLLM([_FakeAIMessage(content="你好，我是助手。")])
    events: list[tuple[str, dict]] = []

    monkeypatch.setattr(module, "save_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "complete_runtime_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "reserve_assistant_model_tokens", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.runtime.events.list_events_after", lambda *args, **kwargs: [])

    harness = StreamingHarness(
        db=object(),  # type: ignore[arg-type]
        user=_FakeUser(),  # type: ignore[arg-type]
        run=_FakeRun(),  # type: ignore[arg-type]
        conversation_id="conv-1",
        llm=llm,
        provider_type="openai",
        provider_source=ProviderSource.OFFICIAL,
        model="test",
        user_message="你好",
        after_sequence=0,
    )

    async def _collect() -> None:
        async for raw in harness.run():
            event_type = ""
            payload = ""
            for line in raw.strip().splitlines():
                if line.startswith("event: "):
                    event_type = line[7:]
                elif line.startswith("data: "):
                    payload = line[6:]
            if event_type and payload:
                events.append((event_type, json.loads(payload)))

    asyncio.run(_collect())

    types = [item[0] for item in events]
    assert "assistant.turn_started" in types
    assert "assistant.message" in types
    assert any(item[0] == "assistant.message" and "你好" in item[1].get("content", "") for item in events)
    assert llm.calls, "model should be invoked once"


def test_streaming_harness_executes_one_correlated_tool_then_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from app.runtime import harness_loop as module
    from app.runtime.registry import PublicCapabilityResult
    from app.usage.schemas import ProviderSource

    class _Action:
        status = "succeeded"

    class _Execution:
        approval = None
        action = _Action()
        result = PublicCapabilityResult("找到 1 个项目。", {"count": 1, "projects": [{"id": "p1", "name": "A"}]})

    llm = _FakeBoundLLM(
        [
            _FakeAIMessage(
                content="",
                tool_calls=[
                    {"id": "call-1", "name": "search_projects", "args": {"query": "demo"}},
                    {"id": "call-2", "name": "list_documents", "args": {"project_id": "p1"}},
                ],
            ),
            _FakeAIMessage(content="我找到了 1 个项目。"),
        ]
    )

    executed: list[str] = []

    def fake_execute_capability(db, user, *, run_id, capability_name, arguments, action_key, executor=None):
        executed.append(capability_name)
        return _Execution()

    monkeypatch.setattr(module, "execute_capability", fake_execute_capability)
    monkeypatch.setattr(module, "save_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "complete_runtime_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "reserve_assistant_model_tokens", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.runtime.events.list_events_after", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "app.runtime.assistant_adapter._render_runtime_event",
        lambda *args, **kwargs: [],
    )

    harness = StreamingHarness(
        db=object(),  # type: ignore[arg-type]
        user=_FakeUser(),  # type: ignore[arg-type]
        run=_FakeRun(),  # type: ignore[arg-type]
        conversation_id="conv-1",
        llm=llm,
        provider_type="openai",
        provider_source=ProviderSource.OFFICIAL,
        model="test",
        user_message="找项目",
    )

    events: list[tuple[str, dict[str, Any]]] = []

    async def _collect() -> None:
        async for raw in harness.run():
            event_type = ""
            payload = ""
            for line in raw.strip().splitlines():
                if line.startswith("event: "):
                    event_type = line[7:]
                elif line.startswith("data: "):
                    payload = line[6:]
            if event_type and payload:
                events.append((event_type, json.loads(payload)))

    asyncio.run(_collect())

    assert executed == ["search_projects"]
    started = next(payload for event, payload in events if event == "assistant.tool_started")
    succeeded = next(payload for event, payload in events if event == "assistant.tool_succeeded")
    assert started["tool_call_id"] == "call-1"
    assert succeeded["tool_call_id"] == "call-1"
    assert started["turn_id"] == succeeded["turn_id"] == "turn-1"
    assert sum(event == "assistant.tool_started" for event, _ in events) == 1
    assert "assistant.turn_finished" in [event for event, _ in events]
    assert "assistant.message" in [event for event, _ in events]
    assert len(llm.calls) == 2


def test_streaming_harness_limits_test_requests_to_read_only_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from app.runtime import harness_loop as module
    from app.usage.schemas import ProviderSource

    llm = _FakeBoundLLM(
        [
            _FakeAIMessage(
                tool_calls=[{"id": "call-create", "name": "create_project", "args": {"name": "不应创建"}}],
            ),
            _FakeAIMessage(content="我只完成了安全的只读诊断。"),
        ]
    )
    executed: list[str] = []

    def fake_execute_capability(*args: Any, **kwargs: Any) -> None:
        executed.append(str(kwargs["capability_name"]))
        raise AssertionError("diagnostic mode must not execute a write capability")

    monkeypatch.setattr(module, "execute_capability", fake_execute_capability)
    monkeypatch.setattr(module, "save_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "complete_runtime_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "reserve_assistant_model_tokens", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.runtime.events.list_events_after", lambda *args, **kwargs: [])

    harness = StreamingHarness(
        db=object(),  # type: ignore[arg-type]
        user=_FakeUser(),  # type: ignore[arg-type]
        run=_FakeRun(),  # type: ignore[arg-type]
        conversation_id="conv-1",
        llm=llm,
        provider_type="openai",
        provider_source=ProviderSource.OFFICIAL,
        model="test",
        user_message="边说边调用工具，随便调用什么都行，我测试你的长任务能力，必须多轮",
    )

    events: list[tuple[str, dict[str, Any]]] = []

    async def _collect() -> None:
        async for raw in harness.run():
            event_type = ""
            payload = ""
            for line in raw.strip().splitlines():
                if line.startswith("event: "):
                    event_type = line[7:]
                elif line.startswith("data: "):
                    payload = line[6:]
            if event_type and payload:
                events.append((event_type, json.loads(payload)))

    asyncio.run(_collect())

    available_names = {tool["function"]["name"] for tool in llm.tools}
    assert "search_projects" in available_names
    assert "create_project" not in available_names
    assert executed == []
    failure = next(payload for event, payload in events if event == "assistant.tool_failed")
    assert "安全诊断" in failure["error_message"]


def test_resume_approval_emits_started_before_succeeded(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from app.runtime import harness_loop as module
    from app.runtime.registry import PublicCapabilityResult
    from app.usage.schemas import ProviderSource
    from contracts.runtime import RuntimeApprovalDecisionType

    class _Action:
        status = "succeeded"

    class _Execution:
        approval = None
        action = _Action()
        result = PublicCapabilityResult("项目已删除。", {"id": "p1"})

    def fake_resolve_approval(db, user, *, approval_id, decision, edited_arguments=None, executor=None):
        assert decision in {
            RuntimeApprovalDecisionType.APPROVE,
            RuntimeApprovalDecisionType.EDIT,
        }
        return _Execution()

    monkeypatch.setattr(module, "resolve_approval", fake_resolve_approval)
    monkeypatch.setattr(module, "save_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "complete_runtime_run", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.runtime.events.list_events_after", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "app.runtime.assistant_adapter._render_runtime_event",
        lambda *args, **kwargs: [],
    )

    harness = StreamingHarness(
        db=object(),  # type: ignore[arg-type]
        user=_FakeUser(),  # type: ignore[arg-type]
        run=_FakeRun(),  # type: ignore[arg-type]
        conversation_id="conv-1",
        llm=_FakeBoundLLM([]),
        provider_type="openai",
        provider_source=ProviderSource.OFFICIAL,
        model="test",
        user_message="确认执行",
    )

    events: list[str] = []

    async def _collect() -> None:
        async for raw in harness.resume_approval(
            approval_id="appr-1",
            approved=True,
            tool_name="delete_project",
            edited_arguments={"project_id": "p1", "confirmation_text": "Demo"},
        ):
            for line in raw.strip().splitlines():
                if line.startswith("event: "):
                    events.append(line[7:])

    asyncio.run(_collect())

    assert events.count("assistant.tool_started") == 1
    assert events.count("assistant.tool_succeeded") == 1
    assert events.count("assistant.end") == 1
    assert events.index("assistant.tool_started") < events.index("assistant.tool_succeeded")
    assert events.index("assistant.tool_succeeded") < events.index("assistant.end")


def test_harness_max_steps_is_bounded() -> None:
    assert HARNESS_MAX_STEPS >= 4
    assert HARNESS_MAX_STEPS <= 12
    assert HARNESS_CAMPAIGN_MAX_STEPS > HARNESS_MAX_STEPS
    assert HARNESS_CAMPAIGN_MAX_STEPS <= 24


def test_product_tool_schemas_include_redraft_feedback_and_export_project() -> None:
    tools = {tool["function"]["name"]: tool["function"]["parameters"] for tool in build_capability_tool_specs()}
    assert "review_feedback" in tools["start_redraft_section"]["properties"]
    assert "project_id" in tools["export_deliverable"]["properties"]
    assert "run_id" in tools["resume_draft_run"]["properties"]
    assert "decision" in tools["resume_draft_run"]["properties"]
    assert set(tools["resume_draft_run"]["required"]) == {"run_id", "decision"}
    assert "mode" in tools["run_section_campaign"]["properties"]
    assert "project_id" in tools["run_section_campaign"]["required"]
