from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from app.models import RuntimeRun
from app.runtime.assistant_adapter import _render_runtime_event
from app.runtime.pi_adapter import _has_visible_text, _text_delta
from app.runtime.service import await_runtime_input
from contracts.pi_runtime import pi_model_provider


def test_whitespace_only_pi_delta_is_not_persisted_as_a_public_event() -> None:
    assert _text_delta(" \t\n") == " \t\n"
    assert _has_visible_text(" \t\n") is False
    assert _has_visible_text("  可展示的文本  ") is True


def test_mimo_direct_balance_uses_pi_builtin_xiaomi_provider() -> None:
    assert pi_model_provider("openai", "mimo", "https://api.xiaomimimo.com/v1") == "xiaomi"
    assert pi_model_provider("openai", "mimo", "https://mimo-gateway.example.test/v1") == "mimo"


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

    assert [event_type for event_type, _payload in events] == ["assistant.session_error", "assistant.end"]
    assert events[0][1]["message"] == "助手运行未完成，已安全停止。"
    assert events[1][1]["state"] == "failed"


def test_terminal_failure_message_is_not_replayed_as_a_normal_assistant_answer() -> None:
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
    assert [event_type for event_type, _payload in events] == ["assistant.start", "assistant.runtime_state"]
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
    monkeypatch.setenv("DOCPILOT_PI_INTERNAL_SECRET", "test-only-pi-bridge-secret-at-least-32-bytes")
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
    assert [event for event, _payload in events] == ["assistant.start", "assistant.runtime_state"]
    assert events[-1][1]["state"] == "queued"


def test_public_assistant_ignores_retired_engine_selector_and_intent_classifier(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DOCPILOT_ASSISTANT_ENGINE", "deterministic")
    monkeypatch.setenv("DOCPILOT_PI_INTERNAL_SECRET", "test-only-pi-bridge-secret-at-least-32-bytes")
    monkeypatch.setattr("app.runtime.pi_adapter.httpx.AsyncClient", _FakePiClient)
    monkeypatch.setattr(
        "app.assistant.runtime.AssistantRuntime.classify",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("retired classifier called")),
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
    assert [event for event, _payload in events] == ["assistant.start", "assistant.runtime_state"]
    assert events[-1][1]["state"] == "queued"
