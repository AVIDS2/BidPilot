"""Unit tests for the streaming harness helpers and multi-step loop."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.runtime.harness_loop import (
    HARNESS_CAMPAIGN_MAX_STEPS,
    HARNESS_MAX_CONSECUTIVE_TOOL_FAILURES,
    HARNESS_MAX_STEPS,
    _TOOL_PARAMETER_SCHEMAS,
    StreamingHarness,
    _mcp_search_payload,
    _extract_public_text_content,
    build_public_reasoning,
    classify_model_failure,
    public_model_failure_message,
    build_capability_tool_specs,
    build_turn_summary,
    resolve_harness_budgets,
)


class _FakeAIMessage:
    def __init__(self, content: Any = "", tool_calls: list[dict[str, Any]] | None = None) -> None:
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


class _FakeStreamChunk:
    def __init__(
        self,
        *,
        content: Any = "",
        reasoning_content: str | None = None,
        tool_call_chunks: list[dict[str, Any]] | None = None,
    ) -> None:
        self.content = content
        self.additional_kwargs = (
            {"reasoning_content": reasoning_content} if reasoning_content is not None else {}
        )
        self.tool_call_chunks = tool_call_chunks or []
        self.usage_metadata = None
        self.response_metadata: dict[str, Any] = {}


class _FakeStreamingBoundLLM:
    def __init__(self, streams: list[list[_FakeStreamChunk]]) -> None:
        self.streams = list(streams)
        self.calls: list[list[Any]] = []

    def bind_tools(self, tools: list[Any]) -> "_FakeStreamingBoundLLM":
        self.tools = tools
        return self

    async def astream(self, messages: list[Any]):
        self.calls.append(messages)
        for chunk in self.streams.pop(0):
            yield chunk


class _FakeRun:
    def __init__(self) -> None:
        self.id = "run-1"
        self.project_id = None
        self.provider_config_id = None
        self.model = "test-model"


class _FakeDb:
    """Small read-only session double for Harness lifecycle-boundary checks."""

    def __init__(self) -> None:
        self.commit_calls = 0
        self.rollback_calls = 0

    def scalar(self, _statement: object) -> str:
        return "running"

    def scalars(self, _statement: object) -> list[object]:
        return []

    def commit(self) -> None:
        self.commit_calls += 1

    def rollback(self) -> None:
        self.rollback_calls += 1


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


def test_section_writing_tools_accept_exact_section_ids() -> None:
    for tool_name in ("start_draft_section", "start_redraft_section", "write_section"):
        assert "section_id" in _TOOL_PARAMETER_SCHEMAS[tool_name]["properties"]


def test_mcp_search_payload_keeps_only_renderable_public_sources() -> None:
    payload = _mcp_search_payload(
        {
            "structured_content": {
                "results": [
                    {
                        "title": "Public procurement guide",
                        "url": "https://example.com/guide",
                        "content": "A source-backed procurement guide.",
                    },
                    {
                        "title": "Unsafe source",
                        "url": "javascript:alert(1)",
                        "content": "Must not reach the replayed trace.",
                    },
                ]
            }
        },
        {"query": "procurement response guide"},
        "tavily",
    )

    assert payload == {
        "query": "procurement response guide",
        "provider": "mcp:tavily",
        "count": 1,
        "items": [
            {
                "title": "Public procurement guide",
                "url": "https://example.com/guide",
                "snippet": "A source-backed procurement guide.",
            }
        ],
    }


def test_build_turn_summary_is_rule_based() -> None:
    summary = build_turn_summary(["search_projects", "search_projects", "list_requirements"])
    assert "搜索项目" in summary
    assert "×2" in summary
    assert "查看需求" in summary


def test_build_public_reasoning_uses_only_safe_model_authored_progress() -> None:
    assert build_public_reasoning(
        ["search_projects"],
        active_project_id=None,
        completed_capabilities=[],
    ) is None

    assert build_public_reasoning(
        ["search_projects"],
        active_project_id=None,
        completed_capabilities=[],
        model_narration="先确认当前工作区有哪些项目，再处理同名项目的范围。",
    ) == "先确认当前工作区有哪些项目，再处理同名项目的范围。"
    assert build_public_reasoning(
        ["search_projects"],
        active_project_id=None,
        completed_capabilities=[],
        model_narration="SERVER_AUTHORIZATION_SCOPE: actor_id=secret",
    ) is None


def test_extract_public_text_content_keeps_text_blocks_and_drops_reasoning() -> None:
    assert _extract_public_text_content([
        {"type": "thinking", "thinking": "private"},
        {"type": "text", "text": "梳理项目范围，确认起草对象。"},
        {"type": "tool_use", "name": "search_projects"},
    ]) == "梳理项目范围，确认起草对象。"


def test_resolve_harness_budgets_raises_for_campaign_language() -> None:
    default_steps, default_tools = resolve_harness_budgets("搜索项目")
    campaign_steps, campaign_tools = resolve_harness_budgets("请把全部章节批量起草")
    assert default_steps == HARNESS_MAX_STEPS
    assert campaign_steps == HARNESS_CAMPAIGN_MAX_STEPS
    # A campaign is one governed capability; its worker owns each internal
    # wave, so the model must not batch unrelated writes in the same turn.
    assert campaign_tools == 1


def test_harness_commits_when_capacity_reservation_is_not_needed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unlimited workspace must not hold the budget row over model I/O."""
    from app.runtime import harness_loop as module
    from app.usage.schemas import ProviderSource

    db = _FakeDb()
    harness = StreamingHarness(
        db=db,  # type: ignore[arg-type]
        user=_FakeUser(),  # type: ignore[arg-type]
        run=_FakeRun(),  # type: ignore[arg-type]
        conversation_id="conv-1",
        llm=_FakeBoundLLM([]),
        provider_type="openai",
        provider_source=ProviderSource.OFFICIAL,
        model="test",
        user_message="检查项目",
        after_sequence=0,
    )
    monkeypatch.setattr(module, "reserve_assistant_model_tokens", lambda *args, **kwargs: None)

    harness._reserve_model_capacity()

    assert db.commit_calls == 1
    assert db.rollback_calls == 0
    assert harness._active_reservation_keys == []


def test_streaming_harness_awaits_mcp_tool_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    from app.runtime import harness_loop as module
    from app.runtime import mcp_client
    from app.usage.schemas import ProviderSource

    async def _specs() -> list[mcp_client.McpToolSpec]:
        return [
            mcp_client.McpToolSpec(
                name="mcp_tavily_search",
                description="Search the public web",
                parameters={"type": "object", "properties": {}},
            )
        ]

    monkeypatch.setattr(mcp_client, "list_mcp_tool_specs", _specs)
    monkeypatch.setattr("app.runtime.harness_loop.reserve_assistant_model_tokens", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.runtime.events.list_events_after", lambda *args, **kwargs: [])
    monkeypatch.setattr("app.runtime.assistant_adapter._render_runtime_event", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "save_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "complete_runtime_run", lambda *args, **kwargs: None)
    llm = _FakeBoundLLM([_FakeAIMessage(content="done")])
    harness = StreamingHarness(
        db=_FakeDb(),  # type: ignore[arg-type]
        user=_FakeUser(),  # type: ignore[arg-type]
        run=_FakeRun(),  # type: ignore[arg-type]
        conversation_id="conv-1",
        llm=llm,
        provider_type="openai",
        provider_source=ProviderSource.OFFICIAL,
        model="test",
        user_message="联网搜索",
    )

    async def _run() -> None:
        async for _event in harness.run():
            pass

    asyncio.run(_run())
    assert "mcp_tavily_search" in {tool["function"]["name"] for tool in llm.tools}


def test_streaming_harness_aborts_an_idle_provider_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A connected-but-silent provider stream must not leave a turn running."""
    import asyncio

    from app.runtime import harness_loop as module
    from app.usage.schemas import ProviderSource

    class _IdleStreamingBoundLLM:
        closed = False

        async def astream(self, _messages: list[Any]):
            try:
                await asyncio.Event().wait()
                yield _FakeStreamChunk(content="unreachable")
            finally:
                self.closed = True

    llm = _IdleStreamingBoundLLM()
    harness = StreamingHarness(
        db=_FakeDb(),  # type: ignore[arg-type]
        user=_FakeUser(),  # type: ignore[arg-type]
        run=_FakeRun(),  # type: ignore[arg-type]
        conversation_id="conv-1",
        llm=llm,
        provider_type="openai",
        provider_source=ProviderSource.OFFICIAL,
        model="test",
        user_message="检查项目",
    )
    monkeypatch.setattr(module, "HARNESS_STREAM_IDLE_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(module, "HARNESS_STREAM_CANCELLATION_POLL_SECONDS", 0.002)

    async def _collect() -> None:
        with pytest.raises(TimeoutError, match="idle"):
            await harness._collect_model_step(llm, [], [], [], turn_id="turn-1")

    asyncio.run(_collect())

    assert llm.closed is True


def test_harness_model_failures_do_not_expose_gateway_model_details() -> None:
    message = public_model_failure_message(
        RuntimeError(
            "Error code: 400 - supported API model names are deepseek-v4-pro, "
            "but you passed deepseek-chat"
        )
    )

    assert "端点不兼容" in message
    assert "deepseek" not in message.lower()


def test_harness_maps_response_format_failures_to_a_recoverable_message() -> None:
    message = public_model_failure_message(
        RuntimeError("This response_format type is unavailable now")
    )

    assert "结构化输出" in message
    assert "response_format" not in message


def test_harness_classifies_provider_failures_with_stable_codes() -> None:
    failure = classify_model_failure(RuntimeError("This response_format type is unavailable now"))

    assert failure.error_code == "provider_structured_output_unsupported"
    assert "response_format" not in failure.message


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
        db=_FakeDb(),  # type: ignore[arg-type]
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
        db=_FakeDb(),  # type: ignore[arg-type]
        user=_FakeUser(),  # type: ignore[arg-type]
        run=_FakeRun(),  # type: ignore[arg-type]
        conversation_id="conv-1",
        llm=llm,
        provider_type="openai",
        provider_source=ProviderSource.OFFICIAL,
        model="test",
        user_message="找项目",
        max_tools_per_turn=1,
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


def test_streaming_harness_chains_bid_discovery_to_draft_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    """A single request can make bounded, result-driven progress through the bid flow."""
    import asyncio

    from app.runtime import harness_loop as module
    from app.runtime.registry import PublicCapabilityResult
    from app.usage.schemas import ProviderSource

    class _Action:
        status = "succeeded"

    class _Execution:
        approval = None
        action = _Action()

        def __init__(self, result: PublicCapabilityResult) -> None:
            self.result = result

    llm = _FakeBoundLLM(
        [
            _FakeAIMessage(tool_calls=[{"id": "call-projects", "name": "search_projects", "args": {}}]),
            _FakeAIMessage(
                tool_calls=[{"id": "call-documents", "name": "list_documents", "args": {"project_id": "p1"}}]
            ),
            _FakeAIMessage(
                tool_calls=[{"id": "call-requirements", "name": "list_requirements", "args": {"project_id": "p1"}}]
            ),
            _FakeAIMessage(
                tool_calls=[{"id": "call-outline", "name": "get_project_outline", "args": {"project_id": "p1"}}]
            ),
            _FakeAIMessage(
                tool_calls=[
                    {
                        "id": "call-draft",
                        "name": "start_draft_section",
                        "args": {"project_id": "p1", "section_key": "technical-approach"},
                    }
                ]
            ),
            _FakeAIMessage(content="已核对项目资料与需求，并启动技术方案章节起草。"),
        ]
    )
    results = {
        "search_projects": PublicCapabilityResult("找到 1 个项目。", {"count": 1, "projects": [{"id": "p1"}]}),
        "list_documents": PublicCapabilityResult("已找到 2 条相关记录。", {"count": 2}),
        "list_requirements": PublicCapabilityResult("找到 3 条需求。", {"count": 3}),
        "get_project_outline": PublicCapabilityResult(
            "大纲共 1 章，已起草 0 章，已批准 0 章。",
            {"project_id": "p1", "sections": [{"section_key": "technical-approach"}]},
        ),
        "start_draft_section": PublicCapabilityResult(
            "起草工作流已启动。",
            {"run_id": "execution-1", "runtime_run_id": "workflow-runtime-1"},
        ),
    }
    executed: list[str] = []
    events: list[tuple[str, dict[str, Any]]] = []

    def fake_execute_capability(_db, _user, *, capability_name, **_kwargs):
        executed.append(capability_name)
        return _Execution(results[capability_name])

    monkeypatch.setattr(module, "execute_capability", fake_execute_capability)
    monkeypatch.setattr(module, "save_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "complete_runtime_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "reserve_assistant_model_tokens", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.runtime.events.list_events_after", lambda *args, **kwargs: [])
    monkeypatch.setattr("app.runtime.assistant_adapter._render_runtime_event", lambda *args, **kwargs: [])

    harness = StreamingHarness(
        db=_FakeDb(),  # type: ignore[arg-type]
        user=_FakeUser(),  # type: ignore[arg-type]
        run=_FakeRun(),  # type: ignore[arg-type]
        conversation_id="conv-1",
        llm=llm,
        provider_type="openai",
        provider_source=ProviderSource.OFFICIAL,
        model="test",
        user_message="检查项目资料和需求后，启动技术方案章节起草。",
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

    assert executed == [
        "search_projects",
        "list_documents",
        "list_requirements",
        "get_project_outline",
        "start_draft_section",
    ]
    assert [payload["tool_name"] for event, payload in events if event == "assistant.tool_started"] == executed
    assert any(event == "assistant.workflow_started" and payload["tool_name"] == "start_draft_section" for event, payload in events)
    final_message_index = next(index for index, (event, _payload) in enumerate(events) if event == "assistant.message")
    last_tool_index = max(index for index, (event, _payload) in enumerate(events) if event == "assistant.tool_succeeded")
    assert last_tool_index < final_message_index
    assert len(llm.calls) == 6


def test_streaming_harness_pauses_for_missing_required_tool_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing required field is recoverable, never a failed mutation."""
    import asyncio

    from app.runtime import harness_loop as module
    from app.usage.schemas import ProviderSource

    llm = _FakeBoundLLM(
        [
            _FakeAIMessage(
                tool_calls=[
                    {"id": "call-create", "name": "create_project", "args": {}},
                ],
            )
        ]
    )
    persisted_state: dict[str, Any] = {}
    saved_messages: list[str] = []

    def fake_set_task_state(_db: Any, _conversation_id: str, **kwargs: Any) -> None:
        persisted_state.update(kwargs)

    def fail_if_executed(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("a tool with missing required input must not execute")

    monkeypatch.setattr(module, "set_task_state", fake_set_task_state)
    monkeypatch.setattr(module, "execute_capability", fail_if_executed)
    monkeypatch.setattr(
        module,
        "save_message",
        lambda _db, _conversation_id, _role, content: saved_messages.append(content),
    )
    monkeypatch.setattr(module, "complete_runtime_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "reserve_assistant_model_tokens", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.runtime.events.list_events_after", lambda *args, **kwargs: [])

    harness = StreamingHarness(
        db=_FakeDb(),  # type: ignore[arg-type]
        user=_FakeUser(),  # type: ignore[arg-type]
        run=_FakeRun(),  # type: ignore[arg-type]
        conversation_id="conv-1",
        llm=llm,
        provider_type="openai",
        provider_source=ProviderSource.OFFICIAL,
        model="test",
        user_message="帮我创建一个项目",
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

    assert persisted_state == {
        "status": "needs_input",
        "tool_name": "create_project",
        "arguments": {},
        "missing_fields": ("name",),
    }
    assert saved_messages == ["请告诉我项目名称。"]
    assert "assistant.tool_started" not in [event for event, _ in events]
    assert "assistant.tool_failed" not in [event for event, _ in events]
    missing = next(payload for event, payload in events if event == "assistant.missing_input")
    assert missing["missing_fields"] == ["name"]
    assert missing["state"] == "needs_input"
    assert events[-1] == (
        "assistant.end",
        {
            "conversation_id": "conv-1",
            "runtime_run_id": "run-1",
            "state": "needs_input",
        },
    )
    assert len(llm.calls) == 1


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
        db=_FakeDb(),  # type: ignore[arg-type]
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


def test_streaming_harness_stops_after_repeated_tool_failures_without_leaking_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    from app.runtime import harness_loop as module
    from app.usage.schemas import ProviderSource

    llm = _FakeBoundLLM(
        [
            _FakeAIMessage(tool_calls=[{"id": f"call-{index}", "name": "search_projects", "args": {}}])
            for index in range(HARNESS_MAX_CONSECUTIVE_TOOL_FAILURES + 1)
        ]
    )
    executed: list[str] = []
    terminal_failures: list[dict[str, Any]] = []
    events: list[tuple[str, dict[str, Any]]] = []

    def _failing_execute(*_args: Any, **kwargs: Any) -> None:
        executed.append(str(kwargs["capability_name"]))
        raise RuntimeError("postgresql://internal-user:super-secret@db.internal/runtime")

    def _fail_runtime(_db: Any, _run_id: str, _message: str, **kwargs: Any) -> None:
        terminal_failures.append(kwargs)

    monkeypatch.setattr(module, "execute_capability", _failing_execute)
    monkeypatch.setattr(module, "fail_runtime_run", _fail_runtime)
    monkeypatch.setattr(module, "save_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "reserve_assistant_model_tokens", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.runtime.events.list_events_after", lambda *args, **kwargs: [])
    monkeypatch.setattr("app.runtime.assistant_adapter._render_runtime_event", lambda *args, **kwargs: [])

    harness = StreamingHarness(
        db=_FakeDb(),  # type: ignore[arg-type]
        user=_FakeUser(),  # type: ignore[arg-type]
        run=_FakeRun(),  # type: ignore[arg-type]
        conversation_id="conv-1",
        llm=llm,
        provider_type="openai",
        provider_source=ProviderSource.OFFICIAL,
        model="test",
        user_message="连续检查项目",
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

    assert executed == ["search_projects"] * HARNESS_MAX_CONSECUTIVE_TOOL_FAILURES
    assert terminal_failures == [{"error_code": "harness_tool_failures", "parent_event_id": None}]
    tool_failures = [payload for event, payload in events if event == "assistant.tool_failed"]
    assert len(tool_failures) == HARNESS_MAX_CONSECUTIVE_TOOL_FAILURES
    assert all("super-secret" not in payload["error_message"] for payload in tool_failures)
    assert all(payload["error_code"] == "capability_execution_failed" for payload in tool_failures)
    assert events[-1] == (
        "assistant.end",
        {
            "conversation_id": "conv-1",
            "runtime_run_id": "run-1",
            "state": "failed",
        },
    )


def test_streaming_harness_stops_immediately_after_remote_import_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed remote fetch must not trigger model-led URL mutation or retries."""
    import asyncio

    from app.runtime import harness_loop as module
    from app.usage.schemas import ProviderSource

    completed: list[str] = []
    saved_messages: list[str] = []
    events: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(module, "complete_runtime_run", lambda _db, _run_id, message, **_kwargs: completed.append(message))
    monkeypatch.setattr(module, "save_message", lambda _db, _conversation_id, _role, message: saved_messages.append(message))
    monkeypatch.setattr("app.runtime.events.list_events_after", lambda *args, **kwargs: [])

    harness = StreamingHarness(
        db=_FakeDb(),  # type: ignore[arg-type]
        user=_FakeUser(),  # type: ignore[arg-type]
        run=_FakeRun(),  # type: ignore[arg-type]
        conversation_id="conv-1",
        llm=_FakeBoundLLM([]),
        provider_type="openai",
        provider_source=ProviderSource.OFFICIAL,
        model="test",
        user_message="下载这个附件",
    )

    async def _collect() -> None:
        async for raw in harness._stop_after_remote_import_failure("目标站点拒绝访问附件。"):
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

    assert len(completed) == 1
    assert saved_messages == completed
    assert "停止自动改写链接、重复搜索或重复下载" in completed[0]
    assert events[-1] == (
        "assistant.end",
        {
            "conversation_id": "conv-1",
            "runtime_run_id": "run-1",
            "state": "completed",
        },
    )


def test_streaming_harness_hides_tool_preface_until_final_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A provider preface cannot appear as a fake answer before a tool runs."""
    import asyncio

    from app.runtime import harness_loop as module
    from app.runtime.registry import PublicCapabilityResult
    from app.usage.schemas import ProviderSource

    class _Action:
        status = "succeeded"

    class _Execution:
        approval = None
        action = _Action()
        result = PublicCapabilityResult("找到 1 个项目。", {"count": 1})

    llm = _FakeBoundLLM(
        [
            _FakeAIMessage(
                content="我先帮你查询项目。",
                tool_calls=[{"id": "call-search", "name": "search_projects", "args": {}}],
            ),
            _FakeAIMessage(content="已找到 1 个项目。"),
        ]
    )

    monkeypatch.setattr(module, "execute_capability", lambda *_args, **_kwargs: _Execution())
    monkeypatch.setattr(module, "save_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "complete_runtime_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "reserve_assistant_model_tokens", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.runtime.events.list_events_after", lambda *args, **kwargs: [])
    monkeypatch.setattr("app.runtime.assistant_adapter._render_runtime_event", lambda *args, **kwargs: [])

    harness = StreamingHarness(
        db=_FakeDb(),  # type: ignore[arg-type]
        user=_FakeUser(),  # type: ignore[arg-type]
        run=_FakeRun(),  # type: ignore[arg-type]
        conversation_id="conv-1",
        llm=llm,
        provider_type="openai",
        provider_source=ProviderSource.OFFICIAL,
        model="test",
        user_message="帮我查看项目",
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

    messages = [payload["content"] for event, payload in events if event == "assistant.message"]
    assert messages == ["已找到 1 个项目。"]
    tool_started = next(index for index, (event, _payload) in enumerate(events) if event == "assistant.tool_started")
    tool_succeeded = next(index for index, (event, _payload) in enumerate(events) if event == "assistant.tool_succeeded")
    final_answer = next(index for index, (event, _payload) in enumerate(events) if event == "assistant.message")
    assert tool_started < tool_succeeded < final_answer


def test_streaming_harness_replaces_provider_reasoning_with_safe_narration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raw provider CoT never crosses the product trace boundary."""
    import asyncio

    from app.runtime import harness_loop as module
    from app.runtime.registry import PublicCapabilityResult
    from app.usage.schemas import ProviderSource

    class _Action:
        status = "succeeded"

    class _Execution:
        approval = None
        action = _Action()
        result = PublicCapabilityResult("找到 1 个项目。", {"count": 1})

    llm = _FakeStreamingBoundLLM(
        [
            [
                _FakeStreamChunk(reasoning_content="先核对当前项目范围。"),
                _FakeStreamChunk(
                    content=[{"type": "text", "text": "梳理项目范围，确认接下来要处理的对象。"}],
                    tool_call_chunks=[
                        {
                            "index": 0,
                            "id": "call-search",
                            "name": "search_projects",
                            "args": "{}",
                        }
                    ],
                ),
            ],
            [_FakeStreamChunk(content="已找到 1 个项目。")],
        ]
    )

    monkeypatch.setattr(module, "execute_capability", lambda *_args, **_kwargs: _Execution())
    monkeypatch.setattr(module, "save_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "complete_runtime_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "reserve_assistant_model_tokens", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.runtime.events.list_events_after", lambda *args, **kwargs: [])
    monkeypatch.setattr("app.runtime.assistant_adapter._render_runtime_event", lambda *args, **kwargs: [])

    harness = StreamingHarness(
        db=_FakeDb(),  # type: ignore[arg-type]
        user=_FakeUser(),  # type: ignore[arg-type]
        run=_FakeRun(),  # type: ignore[arg-type]
        conversation_id="conv-1",
        llm=llm,
        provider_type="openai",
        provider_source=ProviderSource.OFFICIAL,
        model="deepseek-v4-flash",
        user_message="帮我查看项目",
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

    reasoning_index = next(index for index, (event, _payload) in enumerate(events) if event == "assistant.reasoning")
    reasoning_completed_index = next(
        index for index, (event, _payload) in enumerate(events) if event == "assistant.reasoning_completed"
    )
    tool_started_index = next(index for index, (event, _payload) in enumerate(events) if event == "assistant.tool_started")
    final_answer_index = next(index for index, (event, _payload) in enumerate(events) if event == "assistant.message")

    assert events[reasoning_index][1]["content"] == "梳理项目范围，确认接下来要处理的对象。"
    assert events[reasoning_index][1]["title"] == "梳理项目范围，确认接下来要处理的对象。"
    assert events[reasoning_index][1]["source"] == "harness"
    assert all("先核对当前项目范围" not in payload.get("content", "") for _event, payload in events)
    assert reasoning_index < reasoning_completed_index < tool_started_index < final_answer_index
    assert [payload["content"] for event, payload in events if event == "assistant.message"] == ["已找到 1 个项目。"]


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
    monkeypatch.setattr(module, "clear_task_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "save_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "complete_runtime_run", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.runtime.events.list_events_after", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "app.runtime.assistant_adapter._render_runtime_event",
        lambda *args, **kwargs: [],
    )

    harness = StreamingHarness(
        db=_FakeDb(),  # type: ignore[arg-type]
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


def test_harness_max_steps_supports_multi_step_investigation() -> None:
    assert HARNESS_MAX_STEPS >= 20
    assert HARNESS_CAMPAIGN_MAX_STEPS > HARNESS_MAX_STEPS
    assert HARNESS_CAMPAIGN_MAX_STEPS >= 40


def test_product_tool_schemas_include_redraft_feedback_and_export_project() -> None:
    tools = {tool["function"]["name"]: tool["function"]["parameters"] for tool in build_capability_tool_specs()}
    assert "review_feedback" in tools["start_redraft_section"]["properties"]
    assert "project_id" in tools["export_deliverable"]["properties"]
    assert "run_id" in tools["resume_draft_run"]["properties"]
    assert "decision" in tools["resume_draft_run"]["properties"]
    assert set(tools["resume_draft_run"]["required"]) == {"run_id", "decision"}
    assert "mode" in tools["run_section_campaign"]["properties"]
    assert "project_id" in tools["run_section_campaign"]["required"]
    assert "section_version_id" in tools["submit_review_decision"]["properties"]
    assert set(tools["submit_review_decision"]["required"]) == {
        "project_id",
        "section_id",
        "section_version_id",
        "decision",
    }


def test_streaming_harness_ignores_provider_reasoning_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider thought fragments do not affect the public narration."""
    import asyncio

    from app.runtime import harness_loop as module
    from app.runtime.registry import PublicCapabilityResult
    from app.usage.schemas import ProviderSource

    class _Action:
        status = "succeeded"

    class _Execution:
        approval = None
        action = _Action()
        result = PublicCapabilityResult("找到 1 个项目。", {"count": 1})

    llm = _FakeStreamingBoundLLM(
        [
            [
                # Both fragments are deliberately ignored by the Harness.
                _FakeStreamChunk(reasoning_content=" "),
                _FakeStreamChunk(reasoning_content="接下来正常推理。"),
                _FakeStreamChunk(
                    content="我先查询项目。",
                    tool_call_chunks=[
                        {
                            "index": 0,
                            "id": "call-search",
                            "name": "search_projects",
                            "args": "{}",
                        }
                    ],
                ),
            ],
            [_FakeStreamChunk(content="已找到 1 个项目。")],
        ]
    )

    monkeypatch.setattr(module, "execute_capability", lambda *_args, **_kwargs: _Execution())
    monkeypatch.setattr(module, "save_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "complete_runtime_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "reserve_assistant_model_tokens", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.runtime.events.list_events_after", lambda *args, **kwargs: [])
    monkeypatch.setattr("app.runtime.assistant_adapter._render_runtime_event", lambda *args, **kwargs: [])

    harness = StreamingHarness(
        db=_FakeDb(),  # type: ignore[arg-type]
        user=_FakeUser(),  # type: ignore[arg-type]
        run=_FakeRun(),  # type: ignore[arg-type]
        conversation_id="conv-1",
        llm=llm,
        provider_type="openai",
        provider_source=ProviderSource.OFFICIAL,
        model="deepseek-v4-flash",
        user_message="帮我查看项目",
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

    reasoning = [payload["content"] for event, payload in events if event == "assistant.reasoning"]
    assert reasoning == ["我先查询项目。"]
    assert [payload["content"] for event, payload in events if event == "assistant.message"] == ["已找到 1 个项目。"]
