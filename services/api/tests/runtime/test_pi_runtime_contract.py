from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from app.models import RuntimeRun


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
