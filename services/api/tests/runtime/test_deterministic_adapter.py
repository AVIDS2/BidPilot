"""Compatibility tests for the unified deterministic assistant adapter."""

from __future__ import annotations

import json
import uuid

from app.models import AssistantActionAudit, ChatMessage, Project, RuntimeApproval, RuntimeRun
from app.runtime.service import assistant_turn_idempotency_key


def _events(response_text: str) -> list[tuple[str, dict]]:
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


def test_runtime_adapter_persists_safe_read_before_final_message(
    client,
    test_db,
    monkeypatch,
) -> None:
    response = client.post("/assistant/stream", json={"message": "打开项目页面"})

    assert response.status_code == 200
    events = _events(response.text)
    event_names = [event for event, _payload in events]
    start = next(payload for event, payload in events if event == "assistant.start")
    tool_started = next(payload for event, payload in events if event == "assistant.tool_started")
    assert start["runtime_run_id"]
    assert tool_started["runtime_run_id"] == start["runtime_run_id"]
    assert tool_started["runtime_sequence"] == 2
    assert event_names.index("assistant.tool_started") < event_names.index("assistant.message")
    assert event_names.index("assistant.tool_succeeded") < event_names.index("assistant.message")

    runtime_run = test_db.get(RuntimeRun, start["runtime_run_id"])
    assert runtime_run is not None
    assert runtime_run.status == "succeeded"
    assert [event.event_type for event in runtime_run_events(test_db, runtime_run.id)] == [
        "run.started",
        "capability.started",
        "capability.succeeded",
        "message.completed",
        "run.completed",
    ]
    assert test_db.query(AssistantActionAudit).filter_by(conversation_id=start["conversation_id"]).count() == 0


def test_runtime_adapter_replays_duplicate_client_request_without_second_message(
    client,
    test_db,
    default_user_id: str,
    monkeypatch,
) -> None:
    """The deterministic compatibility path keeps the same retry contract as Harness."""
    monkeypatch.setenv("DOCPILOT_ASSISTANT_ENGINE", "deterministic")
    request_id = f"deterministic-retry-{uuid.uuid4().hex}"
    request_body = {"message": "打开项目页面", "client_request_id": request_id}

    first = client.post("/assistant/stream", json=request_body)
    assert first.status_code == 200, first.text
    first_events = _events(first.text)
    first_start = next(payload for event, payload in first_events if event == "assistant.start")
    conversation_id = first_start["conversation_id"]
    runtime_run_id = first_start["runtime_run_id"]
    message_count = test_db.query(ChatMessage).filter_by(conversation_id=conversation_id).count()

    second = client.post("/assistant/stream", json=request_body)
    assert second.status_code == 200, second.text
    second_events = _events(second.text)
    replay_start = next(payload for event, payload in second_events if event == "assistant.start")

    assert replay_start["replayed"] is True
    assert replay_start["runtime_run_id"] == runtime_run_id
    assert test_db.query(ChatMessage).filter_by(conversation_id=conversation_id).count() == message_count
    idempotency_key = assistant_turn_idempotency_key(
        user_id=default_user_id,
        client_request_id=request_id,
    )
    assert test_db.query(RuntimeRun).filter_by(idempotency_key=idempotency_key).count() == 1


def test_runtime_adapter_resumes_generic_approval_without_legacy_audit(
    client,
    test_db,
    monkeypatch,
) -> None:
    project_name = f"Unified Runtime Project {uuid.uuid4().hex[:8]}"

    requested = client.post(
        "/assistant/stream",
        json={"message": f"创建一个项目，名字叫 {project_name}"},
    )

    assert requested.status_code == 200
    requested_events = _events(requested.text)
    confirmation = next(payload for event, payload in requested_events if event == "assistant.confirmation_requested")
    runtime_run_id = confirmation["runtime_run_id"]
    approval = test_db.get(RuntimeApproval, confirmation["approval_id"])
    assert approval is not None
    assert approval.status == "pending"
    assert test_db.get(RuntimeRun, runtime_run_id).status == "awaiting_approval"

    approved = client.post(
        "/assistant/stream",
        json={
            "message": "确认创建项目",
            "conversation_id": confirmation["conversation_id"],
            "confirmation": {
                "approved": True,
                "tool_name": "create_project",
                "arguments": confirmation["arguments"],
                "approval_id": confirmation["approval_id"],
            },
        },
    )

    assert approved.status_code == 200
    approved_events = _events(approved.text)
    assert "assistant.tool_succeeded" in [event for event, _payload in approved_events]
    assert test_db.query(Project).filter_by(name=project_name).one_or_none() is not None

    runtime_run = test_db.get(RuntimeRun, runtime_run_id)
    assert runtime_run is not None
    assert runtime_run.status == "succeeded"
    assert [event.event_type for event in runtime_run_events(test_db, runtime_run.id)] == [
        "run.started",
        "capability.started",
        "approval.requested",
        "approval.resolved",
        "capability.succeeded",
        "message.completed",
        "run.completed",
    ]
    assert test_db.query(AssistantActionAudit).filter_by(conversation_id=confirmation["conversation_id"]).count() == 0


def test_runtime_adapter_queues_memory_graph_only_after_confirmation(
    client,
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    from app.assistant import tools
    from app.memory.schemas import MemoryGraphExtractionRead

    project = Project(
        slug=f"runtime-memory-graph-{uuid.uuid4().hex[:8]}",
        name="Runtime Memory Graph Project",
        scenario_package="bidpilot",
        org_id=default_org_id,
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)

    captured: list[object] = []

    def start_graph(_db, payload, _user):
        captured.append(payload)
        return MemoryGraphExtractionRead(
            run_id="graph-execution-1",
            runtime_run_id="graph-runtime-1",
            project_id=payload.project_id,
            memory_record_id=payload.memory_record_id,
            status="queued",
        )

    monkeypatch.setattr(tools, "start_memory_graph_extraction_command", start_graph)
    memory_record_id = "11111111-1111-1111-1111-111111111111"

    requested = client.post(
        "/assistant/stream",
        json={
            "message": f"为知识记录 {memory_record_id} 生成实体关系提案",
            "project_id": project.id,
        },
    )

    assert requested.status_code == 200
    requested_events = _events(requested.text)
    confirmation = next(payload for event, payload in requested_events if event == "assistant.confirmation_requested")
    assert confirmation["tool_name"] == "propose_memory_graph"
    assert captured == []

    approved = client.post(
        "/assistant/stream",
        json={
            "message": "确认",
            "conversation_id": confirmation["conversation_id"],
            "confirmation": {
                "approved": True,
                "tool_name": "propose_memory_graph",
                "arguments": confirmation["arguments"],
                "approval_id": confirmation["approval_id"],
            },
        },
    )

    assert approved.status_code == 200
    approved_events = _events(approved.text)
    workflow_started = next(payload for event, payload in approved_events if event == "assistant.workflow_started")
    assert workflow_started["tool_name"] == "propose_memory_graph"
    assert workflow_started["result"] == {
        "run_id": "graph-execution-1",
        "runtime_run_id": "graph-runtime-1",
        "reused": False,
    }
    assert "memory_record_id" not in workflow_started["result"]
    assert len(captured) == 1
    assert captured[0].project_id == project.id
    assert captured[0].memory_record_id == memory_record_id


def runtime_run_events(test_db, run_id: str):
    from app.runtime.events import list_events_after

    return list_events_after(test_db, run_id)
