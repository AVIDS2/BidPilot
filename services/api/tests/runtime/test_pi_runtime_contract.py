from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from app.assistant.schemas import AssistantConfirmation
from app.auth.schemas import CurrentUser
from app.models import ChatConversation, ChatMessage, RuntimeRun
from app.runtime import operator_adapter
from app.runtime import assistant_execution
from app.runtime.assistant_adapter import _render_runtime_event
from app.runtime.prompt_assembly import compact_conversation_context
from app.runtime.pi_adapter import (
    _has_visible_text,
    _text_delta,
    stream_pi_assistant_response,
)
from app.runtime.service import await_runtime_input, execute_capability
from app.usage.schemas import ProviderSource
from contracts.pi_runtime import pi_model_provider


def test_whitespace_only_pi_delta_is_not_persisted_as_a_public_event() -> None:
    assert _text_delta(" \t\n") == " \t\n"
    assert _has_visible_text(" \t\n") is False
    assert _has_visible_text("  可展示的文本  ") is True


def test_mimo_direct_balance_uses_pi_builtin_xiaomi_provider() -> None:
    assert (
        pi_model_provider("openai", "mimo", "https://api.xiaomimimo.com/v1") == "xiaomi"
    )
    assert (
        pi_model_provider("openai", "mimo", "https://mimo-gateway.example.test/v1")
        == "mimo"
    )


def test_runtime_run_waiting_for_input_is_not_marked_as_success(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    run = RuntimeRun(
        kind="assistant_turn",
        status="running",
        org_id=default_org_id,
        user_id=default_user_id,
        engine="pi",
        trace_id=f"trace-{uuid4().hex}",
    )
    test_db.add(run)
    test_db.commit()

    await_runtime_input(test_db, run.id)

    test_db.refresh(run)
    assert run.status == "awaiting_input"


def test_queued_pi_executor_forwards_native_events_to_live_sink(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    conversation = ChatConversation(
        id=str(uuid4()),
        user_id=default_user_id,
        title="live event forwarding",
    )
    run = RuntimeRun(
        id=str(uuid4()),
        kind="assistant_turn",
        status="queued",
        org_id=default_org_id,
        user_id=default_user_id,
        conversation_id=conversation.id,
        engine="pi",
        trace_id=f"trace-{uuid4().hex}",
        input_json={"message": "你好"},
    )
    test_db.add_all([conversation, run])
    test_db.commit()

    monkeypatch.setattr(
        assistant_execution,
        "resolve_agent_model",
        lambda: SimpleNamespace(
            provider_type="openai",
            provider_id="test-provider",
            api_key="test-key",
            base_url="https://models.example.test/v1",
            model="test-model",
        ),
    )
    monkeypatch.setattr(
        assistant_execution,
        "load_conversation_context",
        lambda *_args, **_kwargs: compact_conversation_context([]),
    )
    monkeypatch.setattr(
        assistant_execution, "pending_input_context", lambda *_args, **_kwargs: {}
    )
    monkeypatch.setattr(
        assistant_execution, "load_authorized_memory", lambda *_args, **_kwargs: None
    )

    async def no_profile_context(*_args, **_kwargs):
        return []

    monkeypatch.setattr(
        assistant_execution, "load_mem0_profile_context", no_profile_context
    )

    async def fake_pi_stream(*_args, **_kwargs):
        yield 'event: assistant.message\ndata: {"content":"第一段"}\n\n'
        yield 'event: assistant.message\ndata: {"content":"第二段"}\n\n'
        run.status = "succeeded"
        test_db.commit()

    monkeypatch.setattr(
        assistant_execution, "stream_pi_assistant_response", fake_pi_stream
    )

    received: list[str] = []

    async def collect() -> str:
        async def sink(event: str) -> None:
            received.append(event)

        return await assistant_execution.execute_queued_assistant_run(
            test_db,
            run,
            event_sink=sink,
        )

    result = asyncio.run(collect())

    assert result == "succeeded"
    assert received == [
        'event: assistant.message\ndata: {"content":"第一段"}\n\n',
        'event: assistant.message\ndata: {"content":"第二段"}\n\n',
    ]


def test_malformed_structured_confirmation_is_rejected_without_a_new_turn(
    client,
) -> None:
    response = client.post(
        "/assistant/stream",
        json={
            "message": "",
            "confirmation": {
                "approved": True,
                "tool_name": "create_project",
                "arguments": {},
            },
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"]
        == "结构化确认请求缺少 approval_id，未创建新的助手回合。"
    )


def test_pi_approval_continuation_does_not_append_a_fake_user_turn(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    user = CurrentUser(
        id=default_user_id,
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=default_org_id,
    )
    conversation = ChatConversation(
        id=str(uuid4()),
        user_id=default_user_id,
        title="structured approval",
    )
    run = RuntimeRun(
        id=str(uuid4()),
        kind="assistant_turn",
        status="running",
        org_id=default_org_id,
        user_id=default_user_id,
        conversation_id=conversation.id,
        engine="pi",
        trace_id=f"trace-{uuid4().hex}",
        policy_snapshot_json={"approval_mode": "risky_only"},
    )
    test_db.add_all((conversation, run))
    test_db.commit()

    project_name = f"Structured Approval {uuid4().hex[:8]}"
    pending = execute_capability(
        test_db,
        user,
        run_id=run.id,
        capability_name="create_project",
        arguments={"name": project_name, "scenario_package": "bidpilot"},
        action_key="pi-structured-approval",
    )
    assert pending.approval is not None

    async def collect_events() -> list[str]:
        return [
            event
            async for event in operator_adapter._resume_operator_approval(
                test_db,
                user,
                conversation.id,
                AssistantConfirmation(
                    approved=True,
                    tool_name="create_project",
                    # This mirrors an older client and proves the server does
                    # not interpret copied action arguments as an edit.
                    arguments={"name": project_name, "scenario_package": "bidpilot"},
                    approval_id=pending.approval.id,
                ),
                provider_type="openai",
                provider_id=None,
                provider_source=ProviderSource.OFFICIAL,
                api_key="test-key",
                base_url="https://models.example.test/v1",
                model="test-model",
                reasoning_effort="medium",
            )
        ]

    events = asyncio.run(collect_events())

    user_messages = list(
        test_db.query(ChatMessage).filter(
            ChatMessage.conversation_id == conversation.id, ChatMessage.role == "user"
        )
    )
    assert user_messages == []
    assert sum("assistant.tool_succeeded" in event for event in events) == 1
    test_db.refresh(pending.approval)
    test_db.refresh(pending.action)
    test_db.refresh(run)
    assert pending.approval.status == "approved"
    assert pending.action.status == "succeeded"
    assert run.status == "succeeded"


class _FakePiResponse:
    status_code = 200

    async def __aenter__(self) -> _FakePiResponse:
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None

    async def aiter_lines(self):
        for event in (
            {"type": "turn.started", "turn_id": "turn-1"},
            {"type": "text.delta", "delta": "这是一次真实的 Pi 文本响应。"},
            {"type": "agent.completed"},
        ):
            yield json.dumps(event, ensure_ascii=False)


class _FakePiClient:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> _FakePiClient:
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None

    def stream(self, *_args: Any, **_kwargs: Any) -> _FakePiResponse:
        return _FakePiResponse()


class _InterleavedPiResponse(_FakePiResponse):
    async def aiter_lines(self):
        for event in (
            {"type": "turn.started", "turn_id": "turn-1"},
            {"type": "text.delta", "delta": "先检查项目资料。 "},
            {
                "type": "turn.completed",
                "turn_id": "turn-1",
                "text": "先检查项目资料。 ",
            },
            {"type": "turn.started", "turn_id": "turn-2"},
            {"type": "text.delta", "delta": "项目资料已准备好。"},
            {
                "type": "turn.completed",
                "turn_id": "turn-2",
                "text": "项目资料已准备好。",
            },
            {"type": "agent.completed"},
        ):
            yield json.dumps(event, ensure_ascii=False)


class _InterleavedPiClient(_FakePiClient):
    def stream(self, *_args: Any, **_kwargs: Any) -> _InterleavedPiResponse:
        return _InterleavedPiResponse()


def test_pi_turn_persists_each_native_turn_in_history_order(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    conversation = ChatConversation(
        id=str(uuid4()),
        user_id=default_user_id,
        title="native turn order",
    )
    run = RuntimeRun(
        id=str(uuid4()),
        kind="assistant_turn",
        status="running",
        org_id=default_org_id,
        user_id=default_user_id,
        conversation_id=conversation.id,
        engine="pi",
        trace_id=f"trace-{uuid4().hex}",
        input_json={"message": "检查资料"},
        policy_snapshot_json={"approval_mode": "risky_only"},
    )
    test_db.add_all([conversation, run])
    test_db.commit()
    user = CurrentUser(
        id=default_user_id,
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=default_org_id,
    )

    monkeypatch.setenv(
        "DOCPILOT_PI_INTERNAL_SECRET", "test-only-pi-bridge-secret-at-least-32-bytes"
    )
    monkeypatch.setattr(
        "app.runtime.pi_adapter.httpx.AsyncClient", _InterleavedPiClient
    )

    async def no_tools() -> list[dict[str, Any]]:
        return []

    monkeypatch.setattr("app.runtime.pi_adapter._pi_tools_for_run", no_tools)

    async def collect() -> list[str]:
        return [
            event
            async for event in stream_pi_assistant_response(
                test_db,
                user,
                run=run,
                conversation_id=conversation.id,
                provider_type="openai",
                provider_id="test-provider",
                api_key="test-key",
                base_url="http://model.invalid/v1",
                model="test-model",
                user_message="检查资料",
                conversation_window=compact_conversation_context([]),
                memory_context_records=[],
                memory_context_version=None,
                available_attachments=[],
                attachment_context="",
                active_project_id=None,
                pending_input={},
                approval_mode="risky_only",
                reasoning_effort="low",
            )
        ]

    events = asyncio.run(collect())

    messages = (
        test_db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )
    assert [(message.role, message.content) for message in messages] == [
        ("assistant", "先检查项目资料。"),
        ("assistant", "项目资料已准备好。"),
    ]
    assert all(message.runtime_run_id == run.id for message in messages)
    assert sum("assistant.turn_finished" in event for event in events) == 2
    test_db.refresh(run)
    assert run.status == "succeeded"


def test_native_pi_message_is_accepted_without_creating_a_second_runtime_run(
    client,
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    conversation = ChatConversation(
        id=str(uuid4()),
        user_id=default_user_id,
        title="native continuation",
    )
    run = RuntimeRun(
        id=str(uuid4()),
        kind="assistant_turn",
        status="running",
        org_id=default_org_id,
        user_id=default_user_id,
        conversation_id=conversation.id,
        engine="pi",
        trace_id=f"trace-{uuid4().hex}",
    )
    test_db.add_all([conversation, run])
    test_db.commit()
    received: list[tuple[str, str, str]] = []

    async def accept_native_message(
        run_id: str,
        message: str,
        *,
        streaming_behavior: str,
    ) -> bool:
        received.append((run_id, message, streaming_behavior))
        return True

    monkeypatch.setattr(
        "app.assistant.router.request_pi_message", accept_native_message
    )

    response = client.post(
        f"/assistant/runs/{run.id}/messages",
        json={"message": "请优先核对截止时间", "streaming_behavior": "steer"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "accepted",
        "run_id": run.id,
        "streaming_behavior": "steer",
    }
    assert received == [(run.id, "请优先核对截止时间", "steer")]
    assert (
        test_db.query(RuntimeRun)
        .filter(RuntimeRun.conversation_id == conversation.id)
        .count()
        == 1
    )
    messages = (
        test_db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation.id)
        .all()
    )
    assert [
        (message.role, message.content, message.runtime_run_id) for message in messages
    ] == [
        ("user", "请优先核对截止时间", run.id),
    ]


def test_native_pi_message_rejection_rolls_back_the_optimistic_user_message(
    client,
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    conversation = ChatConversation(
        id=str(uuid4()),
        user_id=default_user_id,
        title="rejected native continuation",
    )
    run = RuntimeRun(
        id=str(uuid4()),
        kind="assistant_turn",
        status="running",
        org_id=default_org_id,
        user_id=default_user_id,
        conversation_id=conversation.id,
        engine="pi",
        trace_id=f"trace-{uuid4().hex}",
    )
    test_db.add_all([conversation, run])
    test_db.commit()

    async def reject_native_message(*_args: Any, **_kwargs: Any) -> bool:
        return False

    monkeypatch.setattr(
        "app.assistant.router.request_pi_message", reject_native_message
    )

    response = client.post(
        f"/assistant/runs/{run.id}/messages",
        json={"message": "这条不应进入历史", "streaming_behavior": "steer"},
    )

    assert response.status_code == 409
    assert (
        test_db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation.id)
        .count()
        == 0
    )


def test_local_dev_fallback_can_read_billing_summary(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.auth.router.get_billing_summary",
        lambda *_args, **_kwargs: SimpleNamespace(
            model_dump=lambda: {
                "plan": "professional",
                "status": "active",
            }
        ),
    )

    response = client.get("/auth/billing-summary")

    assert response.status_code == 200
    assert response.json() == {"data": {"plan": "professional", "status": "active"}}


def _sse_events(response_text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for part in response_text.strip().split("\n\n"):
        event_type = ""
        payload = ""
        for line in part.splitlines():
            if line.startswith("event: "):
                event_type = line[7:]
            elif line.startswith("data: "):
                payload = line[6:]
        if event_type and payload:
            events.append((event_type, json.loads(payload)))
    return events


def test_partial_pi_failure_is_projected_as_a_separate_session_error() -> None:
    event = SimpleNamespace(
        id="failed-event",
        run_id="runtime-failed",
        parent_event_id=None,
        sequence=4,
        event_type="run.failed",
        public_summary="任务未能完成。",
        payload_json={
            "kind": "assistant_turn",
            "message": "助手运行未完成，已安全停止。",
            "message_delta_emitted": True,
            "error_code": "assistant_stream_incomplete",
        },
        created_at=None,
    )

    events = _sse_events("".join(_render_runtime_event(event, "conversation-1")))

    assert [event_type for event_type, _payload in events] == [
        "assistant.session_error",
        "assistant.end",
    ]
    assert events[0][1]["message"] == "助手运行未完成，已安全停止。"
    assert events[1][1]["state"] == "failed"


def test_terminal_failure_message_is_not_replayed_as_a_normal_assistant_answer() -> (
    None
):
    event = SimpleNamespace(
        id="failed-message",
        run_id="runtime-failed-message",
        parent_event_id=None,
        sequence=3,
        event_type="message.completed",
        public_summary="模型运行未能完成。",
        payload_json={"terminal_failure": True, "delta_emitted": False},
        created_at=None,
    )

    assert _render_runtime_event(event, "conversation-1") == []


def test_pi_bridge_configuration_failure_stays_inside_sse_contract(
    client,
    test_db,
    monkeypatch,
) -> None:
    """A missing bridge secret is handled by the queued worker boundary, not SSE."""
    monkeypatch.setenv("DOCPILOT_ASSISTANT_ENGINE", "pi")
    monkeypatch.delenv("DOCPILOT_PI_INTERNAL_SECRET", raising=False)
    monkeypatch.delenv("DOCPILOT_JWT_SECRET", raising=False)
    monkeypatch.setattr(
        "app.assistant.router.resolve_agent_model",
        lambda: SimpleNamespace(
            provider_type="openai",
            provider_id="test-provider",
            api_key="test-key",
            base_url="http://model.invalid/v1",
            model="test-model",
        ),
    )

    response = client.post("/assistant/stream", json={"message": "查看当前项目"})

    assert response.status_code == 200
    assert "DOCPILOT_PI_INTERNAL_SECRET" not in response.text
    events = _sse_events(response.text)
    assert [event_type for event_type, _payload in events] == [
        "assistant.start",
        "assistant.runtime_state",
    ]
    assert events[-1][1]["state"] == "queued"
    runtime_run_id = next(
        payload["runtime_run_id"]
        for event, payload in events
        if event == "assistant.start" and "runtime_run_id" in payload
    )
    run = test_db.get(RuntimeRun, runtime_run_id)
    assert run is not None
    assert run.status == "queued"


def test_pi_turn_returns_one_queued_projection_before_worker_execution(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DOCPILOT_ASSISTANT_ENGINE", "pi")
    monkeypatch.setenv(
        "DOCPILOT_PI_INTERNAL_SECRET", "test-only-pi-bridge-secret-at-least-32-bytes"
    )
    monkeypatch.setattr("app.runtime.pi_adapter.httpx.AsyncClient", _FakePiClient)
    monkeypatch.setattr(
        "app.assistant.router.resolve_agent_model",
        lambda: SimpleNamespace(
            provider_type="openai",
            provider_id="test-provider",
            api_key="test-key",
            base_url="http://model.invalid/v1",
            model="test-model",
        ),
    )

    response = client.post(
        "/assistant/stream",
        json={
            "message": "请直接回答，不调用工具。",
            "client_request_id": f"pi-single-terminal-event-{uuid4().hex}",
        },
    )

    assert response.status_code == 200
    events = _sse_events(response.text)
    assert [event for event, _payload in events] == [
        "assistant.start",
        "assistant.runtime_state",
    ]
    assert events[-1][1]["state"] == "queued"


def test_public_assistant_ignores_retired_engine_selector_and_intent_classifier(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DOCPILOT_ASSISTANT_ENGINE", "deterministic")
    monkeypatch.setenv(
        "DOCPILOT_PI_INTERNAL_SECRET", "test-only-pi-bridge-secret-at-least-32-bytes"
    )
    monkeypatch.setattr("app.runtime.pi_adapter.httpx.AsyncClient", _FakePiClient)
    monkeypatch.setattr(
        "app.assistant.runtime.AssistantRuntime.classify",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("retired classifier called")
        ),
    )
    monkeypatch.setattr(
        "app.assistant.router.resolve_agent_model",
        lambda: SimpleNamespace(
            provider_type="openai",
            provider_id="test-provider",
            api_key="test-key",
            base_url="http://model.invalid/v1",
            model="test-model",
        ),
    )

    response = client.post(
        "/assistant/stream",
        json={
            "message": "创建项目 搜索资料 打开画布。这些词不得触发服务端路由。",
            "client_request_id": f"pi-no-retired-router-{uuid4().hex}",
        },
    )

    assert response.status_code == 200
    events = _sse_events(response.text)
    assert [event for event, _payload in events] == [
        "assistant.start",
        "assistant.runtime_state",
    ]
    assert events[-1][1]["state"] == "queued"
