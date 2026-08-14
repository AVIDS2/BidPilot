"""Contract tests for the governed BidPilot adapter beneath the generic loop."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.auth.schemas import CurrentUser
from app.runtime.events import list_events_after
from app.runtime.bidpilot_harness_adapter import BidPilotToolExecutor
from app.runtime.harness_core import HarnessExecutionContext, HarnessToolCall, ToolOutcomeKind
from app.runtime.harness_loop import _TOOL_PARAMETER_SCHEMAS
from app.runtime.registry import PublicCapabilityResult
from app.runtime.service import create_runtime_run


@dataclass
class _Run:
    id: str = "run-1"


class _User:
    id = "user-1"
    org_id = "org-1"
    role = "admin"


class _Db:
    def expire_all(self) -> None:
        self.expired = True


@dataclass
class _Action:
    id: str = "action-1"
    status: str = "pending"
    error_code: str | None = None
    error_message: str | None = None


@dataclass
class _Execution:
    action: _Action
    approval: Any = None
    result: PublicCapabilityResult | None = None


def _call(name: str, arguments: dict[str, Any] | None = None) -> HarnessToolCall:
    return HarnessToolCall(id="call-1", name=name, arguments=arguments or {})


def _context() -> HarnessExecutionContext:
    return HarnessExecutionContext(
        run_id="run-1",
        turn_id="turn-1",
        step=1,
        completed_tool_names=(),
        failed_tool_names=(),
    )


def _adapter(**kwargs: Any) -> BidPilotToolExecutor:
    return BidPilotToolExecutor(
        db=_Db(),  # type: ignore[arg-type]
        user=_User(),  # type: ignore[arg-type]
        runtime_run=_Run(),  # type: ignore[arg-type]
        conversation_id="conversation-1",
        parameter_schemas={
            "list_documents": {"properties": {"project_id": {"type": "string"}}},
            "create_project": {"properties": {"name": {"type": "string"}}},
        },
        **kwargs,
    )


def test_preflight_blocks_an_unregistered_capability_without_an_action() -> None:
    adapter = _adapter()

    outcome = asyncio.run(adapter.prepare(_call("not_a_capability"), _context()))

    assert outcome is not None
    assert outcome.kind is ToolOutcomeKind.BLOCKED
    assert outcome.error_code == "capability_unavailable"


def test_preflight_guard_blocks_before_mcp_or_capability_routing() -> None:
    adapter = _adapter(preflight_guard=lambda _call: "blocked by policy")

    outcome = asyncio.run(adapter.prepare(_call("list_documents"), _context()))

    assert outcome is not None
    assert outcome.kind is ToolOutcomeKind.BLOCKED
    assert outcome.error_code == "capability_policy_blocked"


def test_missing_input_pauses_before_a_mutating_action(monkeypatch) -> None:
    from app.runtime import bidpilot_harness_adapter as module

    persisted: dict[str, Any] = {}
    events: list[Any] = []
    monkeypatch.setattr(module, "set_task_state", lambda *_args, **kwargs: persisted.update(kwargs))
    monkeypatch.setattr(module, "publish_event", lambda *_args, **kwargs: events.append(kwargs["event"]) if "event" in kwargs else events.append(_args[-1]))
    monkeypatch.setattr(module, "prepare_capability_execution", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not prepare")))
    adapter = _adapter()

    outcome = asyncio.run(adapter.prepare(_call("create_project"), _context()))

    assert outcome is not None
    assert outcome.kind is ToolOutcomeKind.PAUSED
    assert outcome.pause_reason == "needs_input"
    assert persisted["missing_fields"] == ("name",)
    assert events and events[0].payload["stage"] == "needs_input"


def test_preflight_persists_action_then_execute_returns_only_public_result(monkeypatch) -> None:
    from app.runtime import bidpilot_harness_adapter as module

    prepared_calls: list[dict[str, Any]] = []
    execution = _Execution(action=_Action(), result=PublicCapabilityResult("找到 2 份资料。", {"count": 2}))

    def fake_prepare(*_args: Any, **kwargs: Any) -> _Execution:
        prepared_calls.append(kwargs)
        return execution

    def fake_execute(*_args: Any, **kwargs: Any) -> _Execution:
        execution.action.status = "succeeded"
        return execution

    monkeypatch.setattr(module, "prepare_capability_execution", fake_prepare)
    monkeypatch.setattr(module, "execute_prepared_capability", fake_execute)
    adapter = _adapter(active_project_id="project-1")

    prepared = asyncio.run(adapter.prepare(_call("list_documents"), _context()))
    outcome = asyncio.run(adapter.execute(_call("list_documents"), _context()))

    assert prepared is None
    assert prepared_calls[0]["arguments"]["project_id"] == "project-1"
    assert outcome.kind is ToolOutcomeKind.SUCCEEDED
    assert outcome.public_summary == "找到 2 份资料。"
    assert outcome.model_payload == {"count": 2}


def test_successful_mutation_is_not_repeated_with_a_new_model_call_id(monkeypatch) -> None:
    """A model retry must not duplicate a committed write in the same run."""
    from app.runtime import bidpilot_harness_adapter as module

    prepared_count = 0
    execution = _Execution(action=_Action(), result=PublicCapabilityResult("项目已创建。", {"id": "project-new"}))

    def fake_prepare(*_args: Any, **_kwargs: Any) -> _Execution:
        nonlocal prepared_count
        prepared_count += 1
        return execution

    def fake_execute(*_args: Any, **_kwargs: Any) -> _Execution:
        execution.action.status = "succeeded"
        return execution

    monkeypatch.setattr(module, "prepare_capability_execution", fake_prepare)
    monkeypatch.setattr(module, "execute_prepared_capability", fake_execute)
    adapter = _adapter()
    monkeypatch.setattr(adapter, "_bind_created_project", lambda *_args: None)
    first = HarnessToolCall(id="call-1", name="create_project", arguments={"name": "同一次运行"})
    repeated = HarnessToolCall(id="call-2", name="create_project", arguments={"name": "同一次运行"})

    assert asyncio.run(adapter.prepare(first, _context())) is None
    assert asyncio.run(adapter.execute(first, _context())).kind is ToolOutcomeKind.SUCCEEDED

    duplicate = asyncio.run(adapter.prepare(repeated, _context()))

    assert duplicate is not None
    assert duplicate.kind is ToolOutcomeKind.SUCCEEDED
    assert "未重复执行" in duplicate.public_summary
    assert prepared_count == 1


def test_approval_is_a_pause_and_never_reaches_execute(monkeypatch) -> None:
    from app.runtime import bidpilot_harness_adapter as module

    approval = type("Approval", (), {"id": "approval-1"})()
    monkeypatch.setattr(
        module,
        "prepare_capability_execution",
        lambda *_args, **_kwargs: _Execution(action=_Action(status="awaiting_approval"), approval=approval),
    )
    adapter = _adapter()

    outcome = asyncio.run(adapter.prepare(_call("create_project", {"name": "新项目"}), _context()))

    assert outcome is not None
    assert outcome.kind is ToolOutcomeKind.PAUSED
    assert outcome.pause_reason == "needs_approval"
    assert outcome.model_payload["approval_id"] == "approval-1"


def test_created_project_binds_the_conversation_once(monkeypatch) -> None:
    from app.runtime import bidpilot_harness_adapter as module

    bound: list[str] = []
    execution = _Execution(action=_Action(), result=PublicCapabilityResult("项目已创建。", {"id": "project-new"}))
    monkeypatch.setattr(module, "prepare_capability_execution", lambda *_args, **_kwargs: execution)
    monkeypatch.setattr(module, "execute_prepared_capability", lambda *_args, **_kwargs: _Execution(action=_Action(status="succeeded"), result=execution.result))
    monkeypatch.setattr(module, "bind_conversation_project_context", lambda *_args, **kwargs: bound.append(kwargs["project_id"]))
    adapter = _adapter(on_project_bound=bound.append)

    assert asyncio.run(adapter.prepare(_call("create_project", {"name": "新项目"}), _context())) is None
    outcome = asyncio.run(adapter.execute(_call("create_project", {"name": "新项目"}), _context()))

    assert outcome.kind is ToolOutcomeKind.SUCCEEDED
    assert adapter.active_project_id == "project-new"
    assert bound == ["project-new", "project-new"]


def test_remote_import_failure_is_not_automatically_retried(monkeypatch) -> None:
    from app.runtime import bidpilot_harness_adapter as module

    execution = _Execution(
        action=_Action(
            status="failed",
            error_code="remote_http_status",
            error_message="目标站点拒绝访问附件。",
        )
    )
    monkeypatch.setattr(module, "prepare_capability_execution", lambda *_args, **_kwargs: _Execution(action=_Action()))
    monkeypatch.setattr(module, "_execute_prepared_in_worker", lambda *_args, **_kwargs: execution)
    adapter = _adapter()

    assert asyncio.run(
        adapter.prepare(_call("fetch_url_to_project", {"project_id": "project-1", "url": "https://example.test/file.zip"}), _context())
    ) is None
    outcome = asyncio.run(
        adapter.execute(_call("fetch_url_to_project", {"project_id": "project-1", "url": "https://example.test/file.zip"}), _context())
    )

    assert outcome.kind is ToolOutcomeKind.FAILED
    assert outcome.recoverable is False
    assert outcome.error_code == "remote_http_status"
    assert "已停止自动重试" in outcome.public_summary


def test_mcp_sensing_tool_uses_the_same_durable_tool_contract(monkeypatch) -> None:
    from app.runtime import bidpilot_harness_adapter as module
    from app.runtime import mcp_client

    events: list[Any] = []
    monkeypatch.setattr(module, "publish_event", lambda *_args, **kwargs: events.append(kwargs.get("event") or _args[-1]))
    monkeypatch.setattr(mcp_client, "parse_mcp_tool_name", lambda _name: ("tavily", "search"))

    async def fake_call(_server: str, _tool: str, _arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "structured_content": {
                "results": [
                    {"title": "Official notice", "url": "https://example.test/notice", "content": "notice text"}
                ]
            }
        }

    monkeypatch.setattr(mcp_client, "call_mcp_tool", fake_call)
    adapter = _adapter()
    tool_call = _call("mcp_tavily_search", {"query": "招标公告"})

    assert asyncio.run(adapter.prepare(tool_call, _context())) is None
    outcome = asyncio.run(adapter.execute(tool_call, _context()))

    assert outcome.kind is ToolOutcomeKind.SUCCEEDED
    assert outcome.model_payload["items"] == [
        {"title": "Official notice", "url": "https://example.test/notice", "snippet": "notice text"}
    ]
    assert [event.type.value for event in events] == ["capability.started", "capability.succeeded"]


def test_real_database_action_is_visible_before_and_after_execution(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    """Exercise the actual action/event lifecycle, not a mocked service call."""
    user = CurrentUser(
        id=default_user_id,
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=default_org_id,
    )
    run = create_runtime_run(
        test_db,
        user,
        kind="assistant_turn",
        engine="streaming_harness",
        approval_mode="full_access",
        input_json={"message": "打开项目页面"},
    )
    adapter = BidPilotToolExecutor(
        db=test_db,
        user=user,
        runtime_run=run,
        conversation_id="missing-conversation-is-not-used-for-navigation",
        parameter_schemas=_TOOL_PARAMETER_SCHEMAS,
        allowed_capabilities=frozenset({"open_page"}),
    )
    tool_call = _call("open_page", {"route": "/projects"})

    assert asyncio.run(adapter.prepare(tool_call, _context())) is None
    event_types_before_execution = [event.event_type for event in list_events_after(test_db, run.id)]
    assert event_types_before_execution == ["run.started", "capability.started"]

    outcome = asyncio.run(adapter.execute(tool_call, _context()))

    assert outcome.kind is ToolOutcomeKind.SUCCEEDED
    assert outcome.model_payload == {"route": "/projects"}
    assert [event.event_type for event in list_events_after(test_db, run.id)] == [
        "run.started",
        "capability.started",
        "capability.succeeded",
    ]
