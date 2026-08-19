"""Governed Pi subagent control-plane contracts."""

from __future__ import annotations

from app.auth.schemas import CurrentUser
from app.models import RuntimeRun, TaskOutboxEvent
from app.runtime.events import list_events_after
from app.runtime.service import create_runtime_run
from app.runtime.subagent_control import create_subagent_runs, wait_for_subagent_results


def _user(org_id: str, user_id: str) -> CurrentUser:
    return CurrentUser(
        id=user_id,
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=org_id,
    )


def test_parallel_subagents_are_durable_and_enqueued(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    user = _user(default_org_id, default_user_id)
    parent = create_runtime_run(test_db, user, kind="assistant_turn", engine="pi")
    dispatched: list[str] = []
    monkeypatch.setattr(
        "app.runtime.subagent_control.request_task_outbox_dispatch",
        lambda event_id: dispatched.append(event_id) or True,
    )

    result = create_subagent_runs(
        test_db,
        user,
        parent_run_id=parent.id,
        arguments={
            "mode": "parallel",
            "tasks": [
                {"agent": "researcher", "task": "查找公开采购公告", "task_id": "research"},
                {"agent": "reviewer", "task": "核查候选公告证据", "task_id": "review"},
            ],
        },
    )

    assert result["status"] == "queued"
    assert len(result["children"]) == 2
    children = test_db.query(RuntimeRun).filter(RuntimeRun.parent_run_id == parent.id).all()
    assert {child.kind for child in children} == {"subagent"}
    assert {child.status for child in children} == {"queued"}
    assert len({child.trace_id for child in children}) == 2
    for child in children:
        contract = child.input_json["subagent"]["pi_runtime"]
        assert contract["version"] == "1"
        assert contract["sandbox"]["hostTools"] == "disabled"
        assert "bidpilot-subagents" in contract["resources"]["extensions"]
    outbox = test_db.query(TaskOutboxEvent).filter(TaskOutboxEvent.runtime_run_id.in_([child.id for child in children])).all()
    assert {event.task_name for event in outbox} == {"worker.run_subagent"}
    assert set(dispatched) == {event.id for event in outbox}
    assert [event.event_type for event in list_events_after(test_db, parent.id)] == [
        "run.started",
        "capability.started",
        "capability.succeeded",
    ]


def test_subagent_delegation_is_idempotent_per_parent_task(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    user = _user(default_org_id, default_user_id)
    parent = create_runtime_run(test_db, user, kind="assistant_turn", engine="pi")
    dispatched: list[str] = []
    monkeypatch.setattr(
        "app.runtime.subagent_control.request_task_outbox_dispatch",
        lambda event_id: dispatched.append(event_id) or True,
    )
    arguments = {"mode": "single", "agent": "researcher", "task": "读取资料", "task_id": "stable"}
    first = create_subagent_runs(test_db, user, parent_run_id=parent.id, arguments=arguments)
    second = create_subagent_runs(test_db, user, parent_run_id=parent.id, arguments=arguments)

    assert first["children"][0]["run_id"] == second["children"][0]["run_id"]
    assert test_db.query(RuntimeRun).filter(RuntimeRun.parent_run_id == parent.id).count() == 1
    assert test_db.query(TaskOutboxEvent).filter(TaskOutboxEvent.runtime_run_id == first["children"][0]["run_id"]).count() == 1
    assert len(dispatched) == 1


def test_chain_children_record_predecessor_dependency(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    user = _user(default_org_id, default_user_id)
    parent = create_runtime_run(test_db, user, kind="assistant_turn", engine="pi")
    monkeypatch.setattr("app.runtime.subagent_control.request_task_outbox_dispatch", lambda *_args: True)
    result = create_subagent_runs(
        test_db,
        user,
        parent_run_id=parent.id,
        arguments={
            "mode": "chain",
            "chain": [
                {"agent": "researcher", "task": "先收集事实", "task_id": "facts"},
                {"agent": "reviewer", "task": "再检查事实", "task_id": "review"},
            ],
        },
    )
    first = test_db.get(RuntimeRun, result["children"][0]["run_id"])
    second = test_db.get(RuntimeRun, result["children"][1]["run_id"])
    assert first is not None and second is not None
    assert first.input_json["subagent"]["previous_child_run_id"] is None
    assert second.input_json["subagent"]["previous_child_run_id"] == first.id


def test_subagent_depth_is_bounded(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    user = _user(default_org_id, default_user_id)
    monkeypatch.setattr("app.runtime.subagent_control.request_task_outbox_dispatch", lambda *_args: True)
    root = create_runtime_run(test_db, user, kind="assistant_turn", engine="pi")
    parent = root
    for index in range(3):
        parent = create_runtime_run(
            test_db,
            user,
            kind="subagent",
            engine="pi_subagent_worker",
            parent_run_id=parent.id,
            idempotency_key=f"manual-depth-{index}",
        )

    try:
        create_subagent_runs(
            test_db,
            user,
            parent_run_id=parent.id,
            arguments={"mode": "single", "task": "不应继续派生"},
        )
    except ValueError as exc:
        assert str(exc) == "subagent_depth_limit"
    else:
        raise AssertionError("depth limit was not enforced")


def test_foreground_wait_returns_ordered_terminal_child_observations(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    user = _user(default_org_id, default_user_id)
    parent = create_runtime_run(test_db, user, kind="assistant_turn", engine="pi")
    monkeypatch.setattr("app.runtime.subagent_control.request_task_outbox_dispatch", lambda *_args: True)
    spawned = create_subagent_runs(
        test_db,
        user,
        parent_run_id=parent.id,
        arguments={
            "mode": "parallel",
            "tasks": [
                {"agent": "researcher", "task": "收集事实", "task_id": "facts"},
                {"agent": "reviewer", "task": "核查事实", "task_id": "review"},
            ],
        },
    )
    first = test_db.get(RuntimeRun, spawned["children"][0]["run_id"])
    second = test_db.get(RuntimeRun, spawned["children"][1]["run_id"])
    assert first is not None and second is not None
    first.status = "succeeded"
    first.result_json = {"summary": "已找到两条可追溯事实。"}
    second.status = "failed"
    second.error_code = "evidence_incomplete"
    second.error_message = "缺少公告原文。"
    test_db.commit()

    result = wait_for_subagent_results(
        test_db,
        user,
        parent_run_id=parent.id,
        child_run_ids=[second.id, first.id],
        timeout_seconds=1,
    )

    assert result["completed"] is True
    assert result["next_step"] == "synthesize_child_results"
    assert [child["task_id"] for child in result["children"]] == ["review", "facts"]
    assert result["children"][0]["error_code"] == "evidence_incomplete"
    assert result["children"][1]["summary"] == "已找到两条可追溯事实。"
