"""Workflow-to-runtime bridge contracts."""

from __future__ import annotations

import asyncio
import inspect
import json
import uuid

from app.auth.schemas import CurrentUser
from app.drafting.schemas import DraftSectionRequest
from app.drafting.service import draft_section_command
from app.drafting.streaming import stream_graph_events
from app.models import ChatConversation, ExecutionRun, Notification, Project, RuntimeRun, TaskOutboxEvent
from app.runtime.background_tasks import collect_completed_notifications
from app.runtime.events import RuntimeEventDraft, list_events_after, publish_event
from app.runtime.service import (
    cancel_runtime_run,
    complete_runtime_run,
    create_runtime_run,
    create_workflow_bridge_run,
    execute_capability,
    list_linked_workflow_runs,
)
from contracts.runtime import RuntimeEventType


def _user(default_org_id: str, default_user_id: str) -> CurrentUser:
    return CurrentUser(
        id=default_user_id,
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=default_org_id,
    )


def test_drafting_command_creates_linked_workflow_runtime_run(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    project = Project(
        slug=f"workflow-bridge-{uuid.uuid4().hex[:8]}",
        name="Workflow Bridge Project",
        scenario_package="bidpilot",
        org_id=default_org_id,
    )
    test_db.add(project)
    test_db.commit()
    dispatched: list[str] = []
    monkeypatch.setattr("app.drafting.service.check_workflow_quota", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "app.drafting.service.request_task_outbox_dispatch",
        lambda event_id: dispatched.append(event_id) or True,
    )

    response = draft_section_command(
        test_db,
        DraftSectionRequest(project_id=project.id, section_key="technical-approach"),
        _user(default_org_id, default_user_id),
    )

    assert response.runtime_run_id
    bridge = test_db.get(RuntimeRun, response.runtime_run_id)
    assert bridge is not None
    assert bridge.kind == "workflow_bridge"
    assert bridge.execution_run_id == response.run_id
    assert bridge.project_id == project.id
    assert [event.event_type for event in list_events_after(test_db, bridge.id)] == ["run.started"]
    outbox_event = test_db.query(TaskOutboxEvent).filter_by(execution_run_id=response.run_id).one()
    assert dispatched == [outbox_event.id]
    assert outbox_event.task_name == "worker.draft_section"
    assert outbox_event.args_json == [response.run_id, project.id, "technical-approach"]
    assert outbox_event.kwargs_json == {"runtime_run_id": bridge.id}


def test_drafting_stream_replays_runtime_events_without_checkpoint_table_reads(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    project = Project(
        slug=f"workflow-stream-{uuid.uuid4().hex[:8]}",
        name="Workflow Stream Project",
        scenario_package="bidpilot",
        org_id=default_org_id,
    )
    test_db.add(project)
    test_db.commit()
    monkeypatch.setattr("app.drafting.service.check_workflow_quota", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.drafting.service.request_task_outbox_dispatch", lambda *_args, **_kwargs: True)
    response = draft_section_command(
        test_db,
        DraftSectionRequest(project_id=project.id, section_key="technical-approach"),
        _user(default_org_id, default_user_id),
    )
    assert response.runtime_run_id
    publish_event(
        test_db,
        response.runtime_run_id,
        RuntimeEventDraft(
            type=RuntimeEventType.CAPABILITY_STARTED,
            public_summary="正在执行章节起草。",
            payload={"capability": "section_drafter", "node": "section_drafter"},
        ),
    )
    publish_event(
        test_db,
        response.runtime_run_id,
        RuntimeEventDraft(
            type=RuntimeEventType.CAPABILITY_SUCCEEDED,
            public_summary="章节草稿已生成。",
            payload={"capability": "section_drafter", "node": "section_drafter"},
        ),
    )
    complete_runtime_run(
        test_db,
        response.runtime_run_id,
        "工作流已完成。",
        result_json={"section_version_id": "version-1"},
    )

    async def collect() -> list[dict[str, str]]:
        return [event async for event in stream_graph_events(response.run_id, test_db)]

    events = asyncio.run(collect())
    decoded = [(event["event"], json.loads(event["data"])) for event in events]
    assert [name for name, _payload in decoded] == [
        "connected",
        "node_started",
        "node_completed",
        "graph_completed",
    ]
    assert decoded[-1][1]["section_version_id"] == "version-1"
    assert "checkpoint_writes" not in inspect.getsource(__import__("app.drafting.streaming", fromlist=["*"]))


def test_drafting_stream_marks_cancelled_workflows_as_cancelled(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    project = Project(
        slug=f"workflow-cancel-{uuid.uuid4().hex[:8]}",
        name="Workflow Cancellation Project",
        scenario_package="bidpilot",
        org_id=default_org_id,
    )
    test_db.add(project)
    test_db.commit()
    monkeypatch.setattr("app.drafting.service.check_workflow_quota", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.drafting.service.request_task_outbox_dispatch", lambda *_args, **_kwargs: True)
    response = draft_section_command(
        test_db,
        DraftSectionRequest(project_id=project.id, section_key="technical-approach"),
        _user(default_org_id, default_user_id),
    )
    assert response.runtime_run_id
    cancel_runtime_run(test_db, response.runtime_run_id, "已取消工作流。")

    async def collect() -> list[dict[str, str]]:
        return [event async for event in stream_graph_events(response.run_id, test_db)]

    events = asyncio.run(collect())
    decoded = [(event["event"], json.loads(event["data"])) for event in events]
    assert [name for name, _payload in decoded] == ["connected", "graph_cancelled"]
    assert decoded[-1][1]["status"] == "cancelled"


def test_runtime_draft_action_links_child_workflow_bridge_to_parent_run(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    project = Project(
        slug=f"workflow-parent-{uuid.uuid4().hex[:8]}",
        name="Workflow Parent Project",
        scenario_package="bidpilot",
        org_id=default_org_id,
    )
    test_db.add(project)
    test_db.commit()
    monkeypatch.setattr("app.drafting.service.check_workflow_quota", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.drafting.service.request_task_outbox_dispatch", lambda *_args, **_kwargs: True)
    user = _user(default_org_id, default_user_id)
    parent = create_runtime_run(
        test_db,
        user,
        kind="assistant_turn",
        engine="deterministic",
        project_id=project.id,
        approval_mode="full_access",
    )

    execution = execute_capability(
        test_db,
        user,
        run_id=parent.id,
        capability_name="start_draft_section",
        arguments={
            "project_id": project.id,
            "section_key": "technical-approach",
            "allow_empty_evidence": True,
        },
        action_key="draft-child-1",
    )

    assert execution.result is not None
    execution_run_id = execution.result.payload["run_id"]
    bridge = test_db.query(RuntimeRun).filter_by(execution_run_id=execution_run_id).one()
    assert bridge.parent_run_id == parent.id
    assert bridge.project_id == project.id
    assert [event.event_type for event in list_events_after(test_db, parent.id)] == [
        "run.started",
        "capability.started",
        "workflow.linked",
        "capability.succeeded",
    ]


def test_runtime_retry_action_returns_a_new_linked_workflow_attempt(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    project = Project(
        slug=f"workflow-retry-{uuid.uuid4().hex[:8]}",
        name="Workflow Retry Project",
        scenario_package="bidpilot",
        org_id=default_org_id,
    )
    test_db.add(project)
    test_db.commit()
    user = _user(default_org_id, default_user_id)
    source = ExecutionRun(
        project_id=project.id,
        run_type="draft_section",
        status="failed",
        input_json={"section_key": "technical-approach"},
    )
    test_db.add(source)
    test_db.commit()
    source_bridge = create_workflow_bridge_run(
        test_db,
        user,
        execution_run_id=source.id,
        project_id=project.id,
    )
    source_bridge.status = "failed"
    test_db.commit()
    parent = create_runtime_run(
        test_db,
        user,
        kind="assistant_turn",
        engine="deterministic",
        project_id=project.id,
        approval_mode="full_access",
    )
    monkeypatch.setattr("app.execution.service.check_workflow_quota", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.execution.service.request_task_outbox_dispatch", lambda *_args, **_kwargs: True)

    execution = execute_capability(
        test_db,
        user,
        run_id=parent.id,
        capability_name="retry_run",
        arguments={"run_id": source.id},
        action_key="retry-child-1",
    )

    assert execution.result is not None
    retry_execution_run_id = execution.result.payload["run_id"]
    retry_runtime_run_id = execution.result.payload["runtime_run_id"]
    retry = test_db.get(ExecutionRun, retry_execution_run_id)
    assert retry is not None
    assert retry.parent_execution_run_id == source.id
    retry_bridge = test_db.get(RuntimeRun, retry_runtime_run_id)
    assert retry_bridge is not None
    assert retry_bridge.parent_run_id == source_bridge.id
    assert [event.event_type for event in list_events_after(test_db, parent.id)] == [
        "run.started",
        "capability.started",
        "capability.succeeded",
    ]


def test_parent_assistant_run_exposes_multiple_linked_workflows(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    project = Project(
        slug=f"workflow-children-{uuid.uuid4().hex[:8]}",
        name="Workflow Children Project",
        scenario_package="bidpilot",
        org_id=default_org_id,
    )
    test_db.add(project)
    test_db.commit()
    user = _user(default_org_id, default_user_id)
    parent = create_runtime_run(
        test_db,
        user,
        kind="assistant_turn",
        engine="streaming_harness",
        project_id=project.id,
        approval_mode="full_access",
    )
    first_execution = ExecutionRun(project_id=project.id, run_type="draft_section", input_json={})
    second_execution = ExecutionRun(project_id=project.id, run_type="draft_section", input_json={})
    test_db.add_all([first_execution, second_execution])
    test_db.flush()
    first = create_workflow_bridge_run(
        test_db,
        user,
        execution_run_id=first_execution.id,
        project_id=project.id,
        parent_run_id=parent.id,
    )
    second = create_workflow_bridge_run(
        test_db,
        user,
        execution_run_id=second_execution.id,
        project_id=project.id,
        parent_run_id=parent.id,
    )

    children = list_linked_workflow_runs(test_db, user, parent_run_id=parent.id)

    assert [child.id for child in children] == [first.id, second.id]
    assert all(child.parent_run_id == parent.id for child in children)
    assert [event.event_type for event in list_events_after(test_db, parent.id)] == [
        "run.started",
        "workflow.linked",
        "workflow.linked",
    ]


def test_durable_workflow_wake_is_consumed_once_by_the_next_assistant_turn(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    project = Project(
        slug=f"workflow-wake-{uuid.uuid4().hex[:8]}",
        name="Workflow Wake Project",
        scenario_package="bidpilot",
        org_id=default_org_id,
    )
    conversation = ChatConversation(user_id=default_user_id, title="Workflow wake")
    test_db.add_all([project, conversation])
    test_db.commit()
    user = _user(default_org_id, default_user_id)
    parent = create_runtime_run(
        test_db,
        user,
        kind="assistant_turn",
        engine="streaming_harness",
        project_id=project.id,
        conversation_id=conversation.id,
        approval_mode="full_access",
    )
    execution = ExecutionRun(project_id=project.id, run_type="draft_section", input_json={})
    test_db.add(execution)
    test_db.flush()
    child = create_workflow_bridge_run(
        test_db,
        user,
        execution_run_id=execution.id,
        project_id=project.id,
        parent_run_id=parent.id,
    )
    complete_runtime_run(test_db, child.id, "章节工作流已完成。", result_json={"section_key": "technical"})
    notification = Notification(
        user_id=user.id,
        type="agent_task",
        title="后台任务已完成",
        body="章节工作流已完成。",
        link=f"/agent?conversation={conversation.id}&wake={child.id}",
    )
    test_db.add(notification)
    test_db.commit()

    first_delivery = collect_completed_notifications(
        test_db,
        conversation_id=conversation.id,
        user_id=user.id,
    )
    second_delivery = collect_completed_notifications(
        test_db,
        conversation_id=conversation.id,
        user_id=user.id,
    )

    assert first_delivery == [
        {
            "task_id": notification.id,
            "kind": "workflow",
            "status": "succeeded",
            "title": "后台任务已完成",
            "detail": {
                "runtime_run_id": child.id,
                "workflow_run_id": execution.id,
                "project_id": project.id,
                "summary": "任务已完成。",
            },
        }
    ]
    assert second_delivery == []
    test_db.refresh(notification)
    assert notification.read is True
