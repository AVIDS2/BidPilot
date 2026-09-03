from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import pytest
from sqlalchemy import select

from app.auth.schemas import CurrentUser
from app.models import (
    AuditEvent,
    ChatConversation,
    ExecutionRun,
    Project,
    RuntimeAction,
    RuntimeRun,
)
from app.runtime.events import list_events_after
from app.runtime.service import (
    RuntimeApprovalExpiredError,
    RuntimeApprovalResolvedError,
    cancel_runtime_run,
    complete_runtime_run,
    create_or_get_runtime_run,
    create_runtime_run,
    create_workflow_bridge_run,
    execute_capability,
    fail_runtime_run,
    get_previous_terminal_action_context,
    reconcile_runtime_run_for_replay,
    request_runtime_cancellation,
    resolve_approval,
    request_workflow_cancellation,
)
from contracts.runtime import (
    RuntimeActionStatus,
    RuntimeApprovalDecisionType,
    RuntimeApprovalStatus,
)


def test_previous_terminal_action_context_is_scoped_and_argument_free(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    conversation_id = str(uuid.uuid4())
    test_db.add(
        ChatConversation(
            id=conversation_id,
            user_id=default_user_id,
            title="failure continuity",
        )
    )
    test_db.flush()
    previous_run = RuntimeRun(
        kind="assistant_turn",
        status="failed",
        org_id=default_org_id,
        user_id=default_user_id,
        conversation_id=conversation_id,
        engine="streaming_harness",
        trace_id=f"trace-{uuid.uuid4().hex}",
        policy_snapshot_json={"approval_mode": "full_access"},
    )
    current_run = RuntimeRun(
        kind="assistant_turn",
        status="running",
        org_id=default_org_id,
        user_id=default_user_id,
        conversation_id=conversation_id,
        engine="streaming_harness",
        trace_id=f"trace-{uuid.uuid4().hex}",
        policy_snapshot_json={"approval_mode": "full_access"},
    )
    test_db.add_all((previous_run, current_run))
    test_db.flush()
    test_db.add(
        RuntimeAction(
            run_id=previous_run.id,
            action_key="failed-create",
            capability_name="create_project",
            status="failed",
            risk_level="low_risk_write",
            policy_outcome="allow",
            approval_mode="full_access",
            arguments_json={"name": "must-not-enter-model-context"},
            error_code="project_limit_exceeded",
            error_message="当前工作区已达到项目数量上限。",
            completed_at=datetime.now(UTC),
        )
    )
    test_db.commit()

    context = get_previous_terminal_action_context(
        test_db,
        _user(default_org_id, default_user_id),
        conversation_id=conversation_id,
        exclude_run_id=current_run.id,
    )

    assert context is not None
    assert context["capability_name"] == "create_project"
    assert context["error_code"] == "project_limit_exceeded"
    assert "arguments" not in context
    assert "must-not-enter-model-context" not in str(context)


def _user(default_org_id: str, default_user_id: str) -> CurrentUser:
    return CurrentUser(
        id=default_user_id,
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=default_org_id,
    )


def _runtime_run(
    test_db, default_org_id: str, default_user_id: str, *, approval_mode: str
) -> RuntimeRun:
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
    run = _runtime_run(
        test_db, default_org_id, default_user_id, approval_mode="full_access"
    )
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


def test_runtime_action_events_keep_turn_and_parent_lineage(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    """Replay can rebuild one public action tree without parsing action keys."""
    run = _runtime_run(
        test_db, default_org_id, default_user_id, approval_mode="full_access"
    )

    execution = execute_capability(
        test_db,
        _user(default_org_id, default_user_id),
        run_id=run.id,
        capability_name="create_project",
        arguments={"name": "Lineage Project"},
        action_key="lineage-tool-call",
        parent_event_id="turn-event-1",
        turn_id="turn-1",
        tool_call_id="pi-call-1",
        executor=lambda _db, _user, arguments: {
            "id": "lineage-project",
            "name": arguments["name"],
            "status": "created",
        },
    )

    assert execution.action.parent_event_id == "turn-event-1"
    assert execution.action.turn_id == "turn-1"
    assert execution.action.tool_call_id == "pi-call-1"
    action_events = [
        event
        for event in list_events_after(test_db, run.id)
        if event.event_type in {"capability.started", "capability.succeeded"}
    ]
    assert [event.event_type for event in action_events] == [
        "capability.started",
        "capability.succeeded",
    ]
    assert all(event.parent_event_id == "turn-event-1" for event in action_events)
    assert all(
        event.payload_json["action_id"] == execution.action.id
        for event in action_events
    )
    assert all(event.payload_json["turn_id"] == "turn-1" for event in action_events)
    assert all(
        event.payload_json["tool_call_id"] == "pi-call-1" for event in action_events
    )


def test_capability_success_keeps_a_result_title_without_breaking_the_trace(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    """A public deliverable title must not collide with event label metadata."""
    project = Project(
        org_id=default_org_id,
        slug=f"event-title-{uuid.uuid4().hex[:8]}",
        name="Event title project",
        scenario_package="bidpilot",
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)
    run = _runtime_run(
        test_db, default_org_id, default_user_id, approval_mode="full_access"
    )
    run.project_id = project.id
    test_db.commit()

    execution = execute_capability(
        test_db,
        _user(default_org_id, default_user_id),
        run_id=run.id,
        capability_name="create_deliverable",
        arguments={"project_id": project.id, "title": "带标题的交付物"},
        action_key="deliverable-title-event",
        executor=lambda _db, _user, _arguments: {
            "id": "deliverable-title-1",
            "title": "带标题的交付物",
            "status": "draft",
        },
    )

    succeeded = [
        event
        for event in list_events_after(test_db, run.id)
        if event.event_type == "capability.succeeded"
    ]
    assert execution.action.status == RuntimeActionStatus.SUCCEEDED.value
    assert len(succeeded) == 1
    assert succeeded[0].payload_json["title"] == "带标题的交付物"


def test_project_scoped_runtime_action_writes_correlation_only_audit_event(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    suffix = uuid.uuid4().hex[:8]
    project = Project(
        org_id=default_org_id,
        name=f"Audit Project {suffix}",
        slug=f"audit-project-{suffix}",
        scenario_package="bidpilot",
    )
    test_db.add(project)
    test_db.flush()
    run = RuntimeRun(
        kind="assistant_turn",
        status="running",
        org_id=default_org_id,
        user_id=default_user_id,
        project_id=project.id,
        engine="deterministic",
        trace_id=f"trace-{uuid.uuid4().hex}",
        policy_snapshot_json={"approval_mode": "full_access"},
    )
    test_db.add(run)
    test_db.commit()

    completed = execute_capability(
        test_db,
        _user(default_org_id, default_user_id),
        run_id=run.id,
        capability_name="create_project",
        arguments={"name": "Correlation only"},
        action_key="correlation-audit",
        executor=lambda *_args: {
            "id": project.id,
            "name": "Correlation only",
            "status": "created",
            "access_token": "must-not-enter-audit",
        },
    )

    audit = test_db.scalar(
        select(AuditEvent).where(
            AuditEvent.project_id == project.id,
            AuditEvent.event_type == "runtime.capability.succeeded",
        )
    )
    assert audit is not None
    assert audit.payload_json == {
        "runtime_run_id": run.id,
        "trace_id": run.trace_id,
        "runtime_action_id": completed.action.id,
        "capability": "create_project",
        "status": "succeeded",
    }
    assert "Correlation only" not in str(audit.payload_json)
    assert "must-not-enter-audit" not in str(audit.payload_json)


def test_capability_failure_persists_a_safe_classified_error(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    run = _runtime_run(
        test_db, default_org_id, default_user_id, approval_mode="full_access"
    )

    def executor(_db, _user, _arguments: dict) -> dict:
        raise RuntimeError("psycopg failure: password=super-secret host=db.internal")

    with pytest.raises(RuntimeError):
        execute_capability(
            test_db,
            _user(default_org_id, default_user_id),
            run_id=run.id,
            capability_name="create_project",
            arguments={"name": "Safe Failure"},
            action_key="safe-failure",
            executor=executor,
        )

    action = test_db.query(RuntimeAction).filter_by(run_id=run.id).one()
    assert action.status == RuntimeActionStatus.FAILED.value
    assert action.error_code == "capability_execution_failed"
    assert action.error_message == "操作未能完成，请稍后重试。"
    assert "super-secret" not in action.error_message

    failure_event = [
        event
        for event in list_events_after(test_db, run.id)
        if event.event_type == "capability.failed"
    ][-1]
    assert failure_event.public_summary == action.error_message
    assert failure_event.payload_json["reason_code"] == action.error_code


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


def test_create_or_get_runtime_run_reports_whether_it_created_the_run(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    user = _user(default_org_id, default_user_id)

    first = create_or_get_runtime_run(
        test_db,
        user,
        kind="assistant_turn",
        engine="streaming_harness",
        idempotency_key=f"assistant-request-{uuid.uuid4()}",
        input_json={"message": "查看项目"},
    )
    second = create_or_get_runtime_run(
        test_db,
        user,
        kind="assistant_turn",
        engine="streaming_harness",
        idempotency_key=first.run.idempotency_key,
        input_json={"message": "查看项目"},
    )

    assert first.created is True
    assert second.created is False
    assert second.run.id == first.run.id
    assert [event.event_type for event in list_events_after(test_db, first.run.id)] == [
        "run.started"
    ]


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


def test_complete_runtime_run_preserves_a_long_pi_answer_without_an_artificial_cap(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    run = create_runtime_run(
        test_db,
        _user(default_org_id, default_user_id),
        kind="assistant_turn",
        engine="pi",
        approval_mode="full_access",
    )
    answer = "资料检查结果：" + "已核实。" * 700

    complete_runtime_run(test_db, run.id, answer, message_delta_emitted=True)

    test_db.refresh(run)
    message_event = next(
        event
        for event in list_events_after(test_db, run.id)
        if event.event_type == "message.completed"
    )
    assert run.status == "succeeded"
    assert run.result_json == {"message": answer}
    assert message_event.public_summary == answer
    assert message_event.payload_json == {
        "message": answer,
        "delta_emitted": True,
        "terminal_failure": False,
    }


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
    assert (failed.status, failed.error_code) == (
        "failed",
        "capability_execution_failed",
    )
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


def test_duplicate_terminal_cancellation_is_idempotent(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    run = create_runtime_run(
        test_db,
        _user(default_org_id, default_user_id),
        kind="assistant_turn",
        engine="pi",
    )
    run.status = "cancel_requested"
    test_db.commit()

    first = cancel_runtime_run(test_db, run.id, "已取消这次操作。")
    second = cancel_runtime_run(test_db, run.id, "已取消这次操作。")

    assert first.status == second.status == "cancelled"
    assert [event.event_type for event in list_events_after(test_db, run.id)] == [
        "run.started",
        "message.completed",
        "run.cancelled",
    ]


def test_cancelling_waiting_approval_closes_the_action_before_it_can_execute(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    user = _user(default_org_id, default_user_id)
    run = _runtime_run(
        test_db, default_org_id, default_user_id, approval_mode="risky_only"
    )
    calls: list[dict] = []

    def executor(_db, _user, arguments: dict) -> dict:
        calls.append(arguments)
        return {"id": "project-1", "name": arguments["name"], "status": "created"}

    pending = execute_capability(
        test_db,
        user,
        run_id=run.id,
        capability_name="create_project",
        arguments={"name": "Cancelled Before Approval"},
        action_key="cancel-waiting-approval",
        executor=executor,
    )
    assert pending.approval is not None

    cancelled = request_runtime_cancellation(test_db, user, run_id=run.id)

    test_db.refresh(run)
    test_db.refresh(pending.action)
    test_db.refresh(pending.approval)
    assert cancelled.status == "cancelled"
    assert run.status == "cancelled"
    assert pending.action.status == RuntimeActionStatus.CANCELLED.value
    assert pending.approval.status == RuntimeApprovalStatus.CANCELLED.value
    assert calls == []
    with pytest.raises(RuntimeApprovalResolvedError):
        resolve_approval(
            test_db,
            user,
            approval_id=pending.approval.id,
            decision=RuntimeApprovalDecisionType.APPROVE,
            executor=executor,
        )
    assert calls == []
    assert [event.event_type for event in list_events_after(test_db, run.id)] == [
        "capability.started",
        "approval.requested",
        "approval.resolved",
        "message.completed",
        "run.cancelled",
    ]


def test_running_assistant_cancellation_is_durable_and_replayable_at_safe_boundary(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    user = _user(default_org_id, default_user_id)
    run = _runtime_run(
        test_db, default_org_id, default_user_id, approval_mode="full_access"
    )

    requested = request_runtime_cancellation(test_db, user, run_id=run.id)
    assert requested.status == "cancel_requested"

    cancelled = reconcile_runtime_run_for_replay(test_db, run.id)
    test_db.refresh(run)
    assert cancelled.status == "cancelled"
    assert run.status == "cancelled"
    assert [event.event_type for event in list_events_after(test_db, run.id)] == [
        "capability.progressed",
        "message.completed",
        "run.cancelled",
    ]


def test_runtime_cancel_api_accepts_an_assistant_turn(
    client,
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    run = _runtime_run(
        test_db, default_org_id, default_user_id, approval_mode="full_access"
    )
    abort_calls: list[str] = []

    async def request_pi_abort(run_id: str) -> bool:
        abort_calls.append(run_id)
        return True

    monkeypatch.setattr("app.runtime.router.request_pi_abort", request_pi_abort)

    response = client.post(f"/runtime/runs/{run.id}/cancel")

    assert response.status_code == 200
    assert response.json()["id"] == run.id
    assert response.json()["status"] == "cancelled"
    assert abort_calls == [run.id]
    test_db.refresh(run)
    assert run.status == "cancelled"


def test_pending_approval_is_reused_and_expired_approval_cannot_execute(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    run = _runtime_run(
        test_db, default_org_id, default_user_id, approval_mode="risky_only"
    )
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

    first.approval.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(
        seconds=1
    )
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
    test_db.refresh(first.action)
    test_db.refresh(run)
    assert first.approval.status == RuntimeApprovalStatus.EXPIRED.value
    assert first.action.status == RuntimeActionStatus.EXPIRED.value
    assert run.status == "expired"
    assert calls == []
    assert [event.event_type for event in list_events_after(test_db, run.id)] == [
        "capability.started",
        "approval.requested",
        "approval.resolved",
        "message.completed",
        "run.failed",
    ]


def test_approved_pending_action_executes_once_and_cannot_be_approved_twice(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    run = _runtime_run(
        test_db, default_org_id, default_user_id, approval_mode="risky_only"
    )
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
    run = _runtime_run(
        test_db, default_org_id, default_user_id, approval_mode="risky_only"
    )

    pending = execute_capability(
        test_db,
        _user(default_org_id, default_user_id),
        run_id=run.id,
        capability_name="create_project",
        arguments={"name": "Reject Through API"},
        action_key="tool-call-rejected",
        executor=lambda *_args: {
            "id": "project-1",
            "name": "Reject Through API",
            "status": "created",
        },
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
    run = _runtime_run(
        test_db, default_org_id, default_user_id, approval_mode="risky_only"
    )
    run.engine = "langgraph_operator"
    test_db.commit()

    pending = execute_capability(
        test_db,
        _user(default_org_id, default_user_id),
        run_id=run.id,
        capability_name="create_project",
        arguments={"name": "Must Resume Graph"},
        action_key="operator-approval",
        executor=lambda *_args: {
            "id": "project-1",
            "name": "Must Resume Graph",
            "status": "created",
        },
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


def test_unlinked_workflow_cancellation_closes_legacy_runtime_row(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    user = _user(default_org_id, default_user_id)
    suffix = uuid.uuid4().hex[:8]
    project = Project(
        org_id=default_org_id,
        name=f"Legacy Cancellation Project {suffix}",
        slug=f"legacy-cancellation-project-{suffix}",
        scenario_package="bidpilot",
    )
    test_db.add(project)
    test_db.flush()
    bridge = create_runtime_run(
        test_db,
        user,
        kind="workflow_bridge",
        engine="langgraph",
        project_id=project.id,
    )
    bridge.status = "awaiting_approval"
    test_db.commit()

    cancelled = request_workflow_cancellation(test_db, user, run_id=bridge.id)

    assert cancelled.status == "cancelled"
    assert [event.event_type for event in list_events_after(test_db, bridge.id)] == [
        "run.started",
        "message.completed",
        "run.cancelled",
    ]
