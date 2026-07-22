from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import pytest

from app.auth.schemas import CurrentUser
from app.models import ExecutionRun, Project, RuntimeRun
from app.runtime.events import list_events_after
from app.runtime.service import (
    RuntimeApprovalExpiredError,
    RuntimeApprovalResolvedError,
    cancel_runtime_run,
    complete_runtime_run,
    create_runtime_run,
    create_workflow_bridge_run,
    execute_capability,
    fail_runtime_run,
    resolve_approval,
    request_workflow_cancellation,
)
from contracts.runtime import RuntimeActionStatus, RuntimeApprovalDecisionType, RuntimeApprovalStatus


def _user(default_org_id: str, default_user_id: str) -> CurrentUser:
    return CurrentUser(
        id=default_user_id,
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=default_org_id,
    )


def _runtime_run(test_db, default_org_id: str, default_user_id: str, *, approval_mode: str) -> RuntimeRun:
    run = RuntimeRun(
        kind="assistant_turn",
        status="running",
        org_id=default_org_id,
        user_id=default_user_id,
        engine="deterministic",
        trace_id=f"trace-{uuid.uuid4().hex}",
        policy_snapshot_json={"approval_mode": approval_mode},
    )
    test_db.add(run)
    test_db.commit()
    test_db.refresh(run)
    return run


def test_action_key_executes_mutation_once_after_replay(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    run = _runtime_run(test_db, default_org_id, default_user_id, approval_mode="full_access")
    calls: list[dict] = []

    def executor(_db, _user, arguments: dict) -> dict:
        calls.append(arguments)
        return {"id": "project-1", "name": arguments["name"], "status": "created"}

    first = execute_capability(
        test_db,
        _user(default_org_id, default_user_id),
        run_id=run.id,
        capability_name="create_project",
        arguments={"name": "Only Once"},
        action_key="tool-call-1",
        executor=executor,
    )
    second = execute_capability(
        test_db,
        _user(default_org_id, default_user_id),
        run_id=run.id,
        capability_name="create_project",
        arguments={"name": "Only Once"},
        action_key="tool-call-1",
        executor=executor,
    )

    assert first.action.status == RuntimeActionStatus.SUCCEEDED.value
    assert second.action.id == first.action.id
    assert calls == [{"name": "Only Once"}]


def test_idempotent_runtime_run_reuses_the_original_started_event(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    user = _user(default_org_id, default_user_id)

    first = create_runtime_run(
        test_db,
        user,
        kind="assistant_turn",
        engine="deterministic",
        idempotency_key="request-123",
        input_json={"message": "查看项目"},
    )
    second = create_runtime_run(
        test_db,
        user,
        kind="assistant_turn",
        engine="deterministic",
        idempotency_key="request-123",
        input_json={"message": "查看项目"},
    )

    assert first.id == second.id
    assert first.status == "running"


def test_complete_runtime_run_persists_message_and_terminal_event(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    run = create_runtime_run(
        test_db,
        _user(default_org_id, default_user_id),
        kind="assistant_turn",
        engine="deterministic",
    )

    complete_runtime_run(test_db, run.id, "已经为你找到项目。")
    complete_runtime_run(test_db, run.id, "不应重复写入。")

    test_db.refresh(run)
    assert run.status == "succeeded"
    assert run.result_json == {"message": "已经为你找到项目。"}
    assert [
        (event.sequence, event.event_type, event.public_summary)
        for event in list_events_after(test_db, run.id)
    ] == [
        (1, "run.started", "任务已开始。"),
        (2, "message.completed", "已经为你找到项目。"),
        (3, "run.completed", "任务已完成。"),
    ]


def test_failed_and_cancelled_runtime_runs_preserve_distinct_terminal_evidence(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    failed = create_runtime_run(
        test_db,
        _user(default_org_id, default_user_id),
        kind="assistant_turn",
        engine="deterministic",
    )
    cancelled = _runtime_run(
        test_db,
        default_org_id,
        default_user_id,
        approval_mode="risky_only",
    )
    cancelled.status = "awaiting_approval"
    test_db.commit()

    fail_runtime_run(
        test_db,
        failed.id,
        "操作未能完成。",
        error_code="capability_execution_failed",
    )
    cancel_runtime_run(test_db, cancelled.id, "已取消这次操作。")

    test_db.refresh(failed)
    test_db.refresh(cancelled)
    assert (failed.status, failed.error_code) == ("failed", "capability_execution_failed")
    assert cancelled.status == "cancelled"
    assert [event.event_type for event in list_events_after(test_db, failed.id)] == [
        "run.started",
        "message.completed",
        "run.failed",
    ]
    assert [event.event_type for event in list_events_after(test_db, cancelled.id)] == [
        "message.completed",
        "run.cancelled",
    ]


def test_pending_approval_is_reused_and_expired_approval_cannot_execute(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    run = _runtime_run(test_db, default_org_id, default_user_id, approval_mode="risky_only")
    calls: list[dict] = []

    def executor(_db, _user, arguments: dict) -> dict:
        calls.append(arguments)
        return {"id": "project-1", "name": arguments["name"], "status": "created"}

    first = execute_capability(
        test_db,
        _user(default_org_id, default_user_id),
        run_id=run.id,
        capability_name="create_project",
        arguments={"name": "Needs Approval"},
        action_key="tool-call-approval",
        executor=executor,
    )
    second = execute_capability(
        test_db,
        _user(default_org_id, default_user_id),
        run_id=run.id,
        capability_name="create_project",
        arguments={"name": "Needs Approval"},
        action_key="tool-call-approval",
        executor=executor,
    )

    assert first.action.status == RuntimeActionStatus.AWAITING_APPROVAL.value
    assert first.approval is not None
    assert second.approval is not None
    assert second.approval.id == first.approval.id
    assert calls == []

    first.approval.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
    test_db.commit()

    with pytest.raises(RuntimeApprovalExpiredError):
        resolve_approval(
            test_db,
            _user(default_org_id, default_user_id),
            approval_id=first.approval.id,
            decision=RuntimeApprovalDecisionType.APPROVE,
            executor=executor,
        )

    test_db.refresh(first.approval)
    assert first.approval.status == RuntimeApprovalStatus.EXPIRED.value
    assert calls == []


def test_approved_pending_action_executes_once_and_cannot_be_approved_twice(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    run = _runtime_run(test_db, default_org_id, default_user_id, approval_mode="risky_only")
    calls: list[dict] = []

    def executor(_db, _user, arguments: dict) -> dict:
        calls.append(arguments)
        return {"id": "project-1", "name": arguments["name"], "status": "created"}

    pending = execute_capability(
        test_db,
        _user(default_org_id, default_user_id),
        run_id=run.id,
        capability_name="create_project",
        arguments={"name": "Approved Once"},
        action_key="tool-call-approved",
        executor=executor,
    )
    assert pending.approval is not None

    completed = resolve_approval(
        test_db,
        _user(default_org_id, default_user_id),
        approval_id=pending.approval.id,
        decision=RuntimeApprovalDecisionType.APPROVE,
        executor=executor,
    )

    assert completed.action.status == RuntimeActionStatus.SUCCEEDED.value
    assert calls == [{"name": "Approved Once"}]

    with pytest.raises(RuntimeApprovalResolvedError):
        resolve_approval(
            test_db,
            _user(default_org_id, default_user_id),
            approval_id=pending.approval.id,
            decision=RuntimeApprovalDecisionType.APPROVE,
            executor=executor,
        )


def test_runtime_approval_api_rejects_pending_action(
    client,
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    run = _runtime_run(test_db, default_org_id, default_user_id, approval_mode="risky_only")

    pending = execute_capability(
        test_db,
        _user(default_org_id, default_user_id),
        run_id=run.id,
        capability_name="create_project",
        arguments={"name": "Reject Through API"},
        action_key="tool-call-rejected",
        executor=lambda *_args: {"id": "project-1", "name": "Reject Through API", "status": "created"},
    )
    assert pending.approval is not None

    response = client.post(
        f"/runtime/approvals/{pending.approval.id}/resolve",
        json={"decision": "reject"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "action_id": pending.action.id,
        "status": "denied",
        "public_summary": None,
        "approval_status": "rejected",
    }


def test_runtime_approval_api_does_not_bypass_an_operator_graph_interrupt(
    client,
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    run = _runtime_run(test_db, default_org_id, default_user_id, approval_mode="risky_only")
    run.engine = "langgraph_operator"
    test_db.commit()

    pending = execute_capability(
        test_db,
        _user(default_org_id, default_user_id),
        run_id=run.id,
        capability_name="create_project",
        arguments={"name": "Must Resume Graph"},
        action_key="operator-approval",
        executor=lambda *_args: {"id": "project-1", "name": "Must Resume Graph", "status": "created"},
    )
    assert pending.approval is not None

    response = client.post(
        f"/runtime/approvals/{pending.approval.id}/resolve",
        json={"decision": "approve"},
    )

    assert response.status_code == 409
    test_db.refresh(pending.action)
    test_db.refresh(pending.approval)
    assert pending.action.status == RuntimeActionStatus.AWAITING_APPROVAL.value
    assert pending.approval.status == RuntimeApprovalStatus.PENDING.value


def test_running_workflow_cancellation_waits_for_the_worker_safe_boundary(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    user = _user(default_org_id, default_user_id)
    suffix = uuid.uuid4().hex[:8]
    project = Project(
        org_id=default_org_id,
        name=f"Cancellation Project {suffix}",
        slug=f"cancellation-project-{suffix}",
        scenario_package="bidpilot",
    )
    test_db.add(project)
    test_db.flush()
    execution = ExecutionRun(
        project_id=project.id,
        run_type="draft_section",
        status="running",
        input_json={"section_key": "technical-approach"},
    )
    test_db.add(execution)
    test_db.commit()

    bridge = create_workflow_bridge_run(
        test_db,
        user,
        execution_run_id=execution.id,
        project_id=project.id,
    )
    cancelled = request_workflow_cancellation(test_db, user, run_id=bridge.id)

    test_db.refresh(execution)
    assert cancelled.status == "cancel_requested"
    assert execution.status == "cancel_requested"
    assert [event.event_type for event in list_events_after(test_db, bridge.id)] == [
        "run.started",
        "capability.progressed",
    ]


def test_queued_workflow_cancellation_is_terminal_and_idempotent(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    user = _user(default_org_id, default_user_id)
    suffix = uuid.uuid4().hex[:8]
    project = Project(
        org_id=default_org_id,
        name=f"Queued Cancellation Project {suffix}",
        slug=f"queued-cancellation-project-{suffix}",
        scenario_package="bidpilot",
    )
    test_db.add(project)
    test_db.flush()
    execution = ExecutionRun(
        project_id=project.id,
        run_type="draft_section",
        status="queued",
        input_json={"section_key": "technical-approach"},
    )
    test_db.add(execution)
    test_db.commit()

    bridge = create_workflow_bridge_run(
        test_db,
        user,
        execution_run_id=execution.id,
        project_id=project.id,
    )
    cancelled = request_workflow_cancellation(test_db, user, run_id=bridge.id)
    repeated = request_workflow_cancellation(test_db, user, run_id=bridge.id)

    test_db.refresh(execution)
    assert cancelled.status == "cancelled"
    assert repeated.status == "cancelled"
    assert execution.status == "cancelled"
    assert [event.event_type for event in list_events_after(test_db, bridge.id)] == [
        "run.started",
        "message.completed",
        "run.cancelled",
    ]
