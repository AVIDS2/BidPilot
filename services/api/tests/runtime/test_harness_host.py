"""Production-host tests: public turns must enter the generic core loop."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.runtime.harness_core import HarnessToolOutcome
from app.runtime.harness_host import CoreStreamingHarness
from app.usage.schemas import ProviderSource


class _FakeRun:
    id = "run-1"
    project_id = None
    provider_config_id = None
    model = "test-model"


class _FakeUser:
    id = "user-1"
    org_id = "org-1"
    email = "dev@docpilot.local"
    display_name = "Dev"
    role = "admin"


class _FakeDb:
    def scalar(self, _statement: object) -> str:
        return "running"

    def scalars(self, _statement: object) -> list[object]:
        return []

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


class _FakeMessage:
    def __init__(self, content: str = "", tool_calls: list[dict[str, Any]] | None = None) -> None:
        self.content = content
        self.tool_calls = tool_calls or []
        self.usage_metadata = None
        self.response_metadata: dict[str, Any] = {}


class _FakeBoundLlm:
    def __init__(self, responses: list[_FakeMessage]) -> None:
        self.responses = responses
        self.calls: list[list[Any]] = []
        self.bind_options: list[dict[str, Any]] = []

    def bind_tools(self, tools: list[dict[str, Any]], **kwargs: Any) -> "_FakeBoundLlm":
        self.tools = tools
        self.bind_options.append(kwargs)
        return self

    def invoke(self, messages: list[Any]) -> _FakeMessage:
        self.calls.append(messages)
        return self.responses.pop(0)


def _harness(llm: _FakeBoundLlm) -> CoreStreamingHarness:
    return CoreStreamingHarness(
        db=_FakeDb(),  # type: ignore[arg-type]
        user=_FakeUser(),  # type: ignore[arg-type]
        run=_FakeRun(),  # type: ignore[arg-type]
        conversation_id="conversation-1",
        llm=llm,
        provider_type="openai",
        provider_source=ProviderSource.OFFICIAL,
        model="test-model",
        user_message="请帮忙处理",
    )


def _event_types(raw_events: list[str]) -> list[str]:
    return [
        next(line[7:] for line in raw.splitlines() if line.startswith("event: "))
        for raw in raw_events
        if "event: " in raw
    ]


def test_core_host_handles_a_plain_conversation_without_reentering_legacy_loop(monkeypatch) -> None:
    from app.runtime import background_tasks, harness_loop

    monkeypatch.setattr(background_tasks, "collect_completed_notifications", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(harness_loop, "record_runtime_context_trace", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(harness_loop, "reserve_assistant_model_tokens", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.runtime.harness_host.save_message", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.runtime.harness_host.complete_runtime_run", lambda *_args, **_kwargs: None)
    llm = _FakeBoundLlm([_FakeMessage("已收到，我可以协助处理。")])

    async def collect() -> list[str]:
        return [event async for event in _harness(llm).run()]

    raw_events = asyncio.run(collect())

    assert _event_types(raw_events) == ["assistant.turn_started", "assistant.message", "assistant.end"]
    assert len(llm.calls) == 1


def test_core_host_projects_a_governed_tool_turn_in_core_order(monkeypatch) -> None:
    from app.runtime import background_tasks, harness_host, harness_loop

    class _ToolExecutor:
        async def prepare(self, _call, _context):
            return None

        async def execute(self, _call, _context):
            return HarnessToolOutcome.succeeded("找到 1 个项目。", {"count": 1})

    monkeypatch.setattr(background_tasks, "collect_completed_notifications", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(harness_loop, "record_runtime_context_trace", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(harness_loop, "reserve_assistant_model_tokens", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(harness_host, "BidPilotToolExecutor", lambda **_kwargs: _ToolExecutor())
    monkeypatch.setattr(harness_host, "save_message", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(harness_host, "complete_runtime_run", lambda *_args, **_kwargs: None)
    llm = _FakeBoundLlm(
        [
            _FakeMessage("", [{"id": "call-1", "name": "search_projects", "args": {"query": "演示"}}]),
            _FakeMessage("已找到 1 个项目。"),
        ]
    )

    async def collect() -> list[str]:
        return [event async for event in _harness(llm).run()]

    raw_events = asyncio.run(collect())
    types = _event_types(raw_events)

    assert types.index("assistant.tool_started") < types.index("assistant.tool_succeeded") < types.index("assistant.message")
    assert types.index("assistant.plan_updated") < types.index("assistant.tool_started")
    assert types[-1] == "assistant.end"
    assert len(llm.calls) == 2
    plan_event = next(event for event in raw_events if "assistant.plan_updated" in event)
    plan_payload = json.loads(next(line[6:] for line in plan_event.splitlines() if line.startswith("data: ")))
    assert plan_payload["summary"] == "执行计划：搜索项目。"
    assert plan_payload["items"] == [
        {
            "id": "call-1",
            "capability": "search_projects",
            "title": "搜索项目",
            "status": "planned",
            "turn_id": "turn-1",
        }
    ]
    tool_success = next(event for event in raw_events if "assistant.tool_succeeded" in event)
    payload = json.loads(next(line[6:] for line in tool_success.splitlines() if line.startswith("data: ")))
    assert payload["result"] == {"count": 1}


def test_core_host_emits_confirmation_end_for_approval_pause(monkeypatch) -> None:
    from app.runtime import background_tasks, harness_host, harness_loop

    class _ToolExecutor:
        async def prepare(self, _call, _context):
            return HarnessToolOutcome.paused("需要确认", pause_reason="needs_approval")

        async def execute(self, _call, _context):
            raise AssertionError("approval pause must not execute")

    monkeypatch.setattr(background_tasks, "collect_completed_notifications", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(harness_loop, "record_runtime_context_trace", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(harness_loop, "reserve_assistant_model_tokens", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(harness_host, "BidPilotToolExecutor", lambda **_kwargs: _ToolExecutor())
    monkeypatch.setattr(harness_host, "publish_event", lambda *_args, **_kwargs: None)
    llm = _FakeBoundLlm([_FakeMessage("", [{"id": "call-1", "name": "create_project", "args": {"name": "x"}}])])

    async def collect() -> list[str]:
        return [event async for event in _harness(llm).run()]

    raw_events = asyncio.run(collect())
    assert _event_types(raw_events)[-1] == "assistant.end"
    end_event = next(event for event in raw_events if "event: assistant.end" in event)
    payload = json.loads(next(line[6:] for line in end_event.splitlines() if line.startswith("data: ")))
    assert payload["state"] == "needs_confirmation"


def test_core_host_never_forces_a_tool_call_from_message_keywords(monkeypatch) -> None:
    """The model protocol, not server-side word matching, owns action selection."""
    from app.runtime import background_tasks, harness_loop

    monkeypatch.setattr(background_tasks, "collect_completed_notifications", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(harness_loop, "record_runtime_context_trace", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(harness_loop, "reserve_assistant_model_tokens", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.runtime.harness_host.save_message", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.runtime.harness_host.complete_runtime_run", lambda *_args, **_kwargs: None)
    llm = _FakeBoundLlm([_FakeMessage("我还缺少足够信息，先不执行。")])
    harness = _harness(llm)
    harness.user_message = "创建、执行、导入、下载、确认"

    async def collect() -> list[str]:
        return [event async for event in harness.run()]

    raw_events = asyncio.run(collect())

    assert len(llm.calls) == 1
    assert llm.bind_options == [{}]
    end_event = next(event for event in raw_events if "event: assistant.end" in event)
    payload = json.loads(next(line[6:] for line in end_event.splitlines() if line.startswith("data: ")))
    assert payload["state"] == "completed"
