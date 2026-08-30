"""Durable Worker execution for governed Pi child agents."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from celery.exceptions import Retry

import app.tasks as task_module
from app.db import SessionLocal
from app.models import ChatConversation, ChatMessage, Organization, RuntimeEvent, RuntimeRun, User


class _FakeStreamResponse:
    def __init__(self, events: list[dict[str, object]]) -> None:
        self._events = events

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        for event in self._events:
            yield json.dumps(event)


class _FakeAsyncClient:
    def __init__(self, captured: list[dict[str, object]], events: list[dict[str, object]], **_kwargs) -> None:
        self._captured = captured
        self._events = events

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    def stream(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, object],
        headers: dict[str, str] | None = None,
    ):
        self._captured.append({"method": method, "url": url, "request": json, "headers": headers or {}})
        return _FakeStreamResponse(self._events)


def test_chain_subagent_receives_previous_result_and_persists_terminal_state(monkeypatch) -> None:
    suffix = uuid.uuid4().hex[:8]
    completed_deliveries: list[str | None] = []
    observed_start_statuses: list[str] = []
    captured: list[dict[str, object]] = []
    events = [
        {"type": "tool.started", "name": "web_search", "tool_call_id": "call-1"},
        {
            "type": "tool.completed",
            "name": "web_search",
            "tool_call_id": "call-1",
            "is_error": False,
        },
        {"type": "text.delta", "delta": "复核完成：证据一致。"},
        {"type": "agent.completed"},
    ]
    db = SessionLocal()
    try:
        org = Organization(slug=f"subagent-{suffix}", name="Subagent Test")
        db.add(org)
        db.flush()
        user = User(
            org_id=org.id,
            email=f"subagent-{suffix}@example.test",
            display_name="Subagent Test",
            role="admin",
            password_hash="test-only",
            email_verified=True,
        )
        db.add(user)
        db.flush()
        conversation = ChatConversation(user_id=user.id, title="Child run")
        db.add(conversation)
        db.flush()
        previous = RuntimeRun(
            kind="subagent",
            status="succeeded",
            org_id=org.id,
            user_id=user.id,
            conversation_id=conversation.id,
            engine="pi_subagent_worker",
            trace_id=f"previous-{suffix}",
            result_json={"summary": "已核实公告原文和截止时间。"},
            policy_snapshot_json={},
        )
        db.add(previous)
        db.flush()
        child = RuntimeRun(
            kind="subagent",
            status="queued",
            org_id=org.id,
            user_id=user.id,
            conversation_id=conversation.id,
            engine="pi_subagent_worker",
            trace_id=f"child-{suffix}",
            reasoning_effort="extra",
            policy_snapshot_json={},
            input_json={
                "subagent": {
                    "profile": "reviewer",
                    "prompt": "复核这份结论：{previous}",
                    "previous_child_run_id": previous.id,
                    "max_steps": 6,
                    "pi_runtime": {
                        "version": "1",
                        "tools": [],
                        "resources": {"extensions": ["bidpilot-subagents"], "skills": []},
                        "sandbox": {"profile": "governed_cloud", "hostTools": "disabled"},
                    },
                },
            },
        )
        db.add(child)
        db.commit()
        child_id = child.id
    finally:
        db.close()

    monkeypatch.setenv("DOCPILOT_PI_INTERNAL_SECRET", "test-only-pi-bridge-secret-at-least-32-bytes")
    monkeypatch.setattr(task_module, "claim_workflow_task_delivery", lambda *_args: True)
    monkeypatch.setattr(
        task_module,
        "complete_workflow_task_delivery",
        lambda event_id: completed_deliveries.append(event_id),
    )
    monkeypatch.setattr(task_module, "fail_workflow_task_delivery", lambda *_args: None)
    monkeypatch.setattr(
        "app.runtime.model_impl.resolve_agent_model",
        lambda **_kwargs: SimpleNamespace(
            provider_id="test",
            provider_type="openai",
            model="test-model",
            base_url="https://models.example.test/v1",
            api_key="test-model-key",
        ),
    )
    def client_factory(**kwargs):
        verify_db = SessionLocal()
        try:
            observed = verify_db.get(RuntimeRun, child_id)
            observed_start_statuses.append(observed.status if observed is not None else "missing")
        finally:
            verify_db.close()
        return _FakeAsyncClient(captured, events, **kwargs)

    monkeypatch.setattr(task_module.httpx, "AsyncClient", client_factory)

    result = task_module.run_subagent(child_id, outbox_event_id="outbox-test")

    assert result["status"] == "succeeded"
    assert completed_deliveries == ["outbox-test"]
    assert observed_start_statuses == ["running"]
    request = captured[0]["request"]
    assert captured[0]["headers"] == {
        "Authorization": "Bearer test-only-pi-bridge-secret-at-least-32-bytes",
    }
    assert request["userMessage"] == "复核这份结论：已核实公告原文和截止时间。"
    assert request["model"]["thinkingLevel"] == "high"
    assert request["maxTurns"] == 6
    db = SessionLocal()
    try:
        persisted = db.get(RuntimeRun, child_id)
        assert persisted is not None
        assert persisted.status == "succeeded"
        assert persisted.result_json["summary"] == "复核完成：证据一致。"
        messages = db.query(ChatMessage).filter(ChatMessage.runtime_run_id == child_id).all()
        assert [message.content for message in messages] == ["复核完成：证据一致。"]
        progress_events = (
            db.query(RuntimeEvent)
            .filter(
                RuntimeEvent.run_id == child_id,
                RuntimeEvent.event_type == "capability.progressed",
            )
            .order_by(RuntimeEvent.sequence.asc())
            .all()
        )
        assert [event.payload_json["phase"] for event in progress_events] == [
            "tool_started",
            "tool_completed",
        ]
        assert all(event.payload_json["tool"] == "web_search" for event in progress_events)
        assert all("arguments" not in event.payload_json for event in progress_events)
        assert all("result" not in event.payload_json for event in progress_events)
    finally:
        db.close()


def test_chain_subagent_waits_with_celery_retry_instead_of_failing(monkeypatch) -> None:
    suffix = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        org = Organization(slug=f"subagent-wait-{suffix}", name="Subagent Wait Test")
        db.add(org)
        db.flush()
        user = User(
            org_id=org.id,
            email=f"subagent-wait-{suffix}@example.test",
            display_name="Subagent Wait Test",
            role="admin",
            password_hash="test-only",
            email_verified=True,
        )
        db.add(user)
        db.flush()
        previous = RuntimeRun(
            kind="subagent",
            status="running",
            org_id=org.id,
            user_id=user.id,
            engine="pi_subagent_worker",
            trace_id=f"previous-wait-{suffix}",
            policy_snapshot_json={},
        )
        db.add(previous)
        db.flush()
        child = RuntimeRun(
            kind="subagent",
            status="queued",
            org_id=org.id,
            user_id=user.id,
            engine="pi_subagent_worker",
            trace_id=f"child-wait-{suffix}",
            policy_snapshot_json={},
            input_json={"subagent": {"previous_child_run_id": previous.id}},
        )
        db.add(child)
        db.commit()
        child_id = child.id
    finally:
        db.close()

    failed: list[str] = []
    claimed: list[str | None] = []
    monkeypatch.setattr(
        task_module,
        "claim_workflow_task_delivery",
        lambda event_id: claimed.append(event_id) or True,
    )
    monkeypatch.setattr(task_module, "fail_runtime_run", lambda *_args, **_kwargs: failed.append("failed"))
    monkeypatch.setattr(task_module, "fail_workflow_task_delivery", lambda *_args: failed.append("outbox-failed"))

    with pytest.raises(Retry):
        task_module.run_subagent(child_id, outbox_event_id="outbox-wait")
    assert failed == []
    assert claimed == []
