"""Pi bridge delegation stays inside the durable tenant-scoped control plane."""

from app.auth.schemas import CurrentUser
from app.models import RuntimeRun
from app.runtime.pi_bridge import PiBridgeToolCall, create_pi_bridge_token, execute_pi_tool
from app.runtime.service import create_runtime_run


def _user(org_id: str, user_id: str) -> CurrentUser:
    return CurrentUser(
        id=user_id,
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=org_id,
    )


def test_pi_bridge_queues_tenant_scoped_subagent(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DOCPILOT_PI_INTERNAL_SECRET", "test-only-pi-bridge-secret-at-least-32-bytes")
    monkeypatch.setattr("app.runtime.subagent_control.request_task_outbox_dispatch", lambda *_args: True)
    user = _user(default_org_id, default_user_id)
    parent = create_runtime_run(test_db, user, kind="assistant_turn", engine="pi")
    token = create_pi_bridge_token(run=parent, user=user)

    result = execute_pi_tool(
        PiBridgeToolCall(
            run_id=parent.id,
            tool_call_id="delegate-1",
            name="spawn_subagents",
            arguments={
                "mode": "single",
                "agent": "researcher",
                "task": "核查公告证据",
                "completion": "background",
            },
        ),
        authorization=f"Bearer {token}",
    )

    assert result["kind"] == "succeeded"
    child_id = result["modelPayload"]["children"][0]["run_id"]
    child = test_db.get(RuntimeRun, child_id)
    assert child is not None
    test_db.refresh(child)
    assert child.parent_run_id == parent.id
    assert child.org_id == user.org_id
    assert child.user_id == user.id
    assert child.kind == "subagent"
    assert child.status == "queued"


def test_pi_bridge_foreground_delegation_returns_child_results(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DOCPILOT_PI_INTERNAL_SECRET", "test-only-pi-bridge-secret-at-least-32-bytes")
    monkeypatch.setattr("app.runtime.subagent_control.request_task_outbox_dispatch", lambda *_args: True)
    monkeypatch.setattr(
        "app.runtime.pi_bridge.wait_for_subagent_results",
        lambda *_args, **_kwargs: {
            "status": "completed",
            "completed": True,
            "children": [
                {
                    "run_id": "child-finished",
                    "task_id": "research",
                    "profile": "researcher",
                    "status": "succeeded",
                    "summary": "已核查公告原文。",
                    "error_code": None,
                }
            ],
            "resumable": False,
            "next_step": "synthesize_child_results",
        },
    )
    user = _user(default_org_id, default_user_id)
    parent = create_runtime_run(test_db, user, kind="assistant_turn", engine="pi")
    token = create_pi_bridge_token(run=parent, user=user)

    result = execute_pi_tool(
        PiBridgeToolCall(
            run_id=parent.id,
            tool_call_id="delegate-foreground",
            name="spawn_subagents",
            arguments={"mode": "single", "agent": "researcher", "task": "核查公告原文"},
        ),
        authorization=f"Bearer {token}",
    )

    assert result["kind"] == "succeeded"
    assert result["recoverable"] is False
    assert result["modelPayload"]["completed"] is True
    assert result["modelPayload"]["children"][0]["summary"] == "已核查公告原文。"
    assert result["publicPayload"]["children"] == [
        {"run_id": "child-finished", "status": "succeeded"}
    ]


def test_pi_bridge_rejects_subagent_run_scope_mismatch(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    from fastapi import HTTPException

    monkeypatch.setenv("DOCPILOT_PI_INTERNAL_SECRET", "test-only-pi-bridge-secret-at-least-32-bytes")
    user = _user(default_org_id, default_user_id)
    parent = create_runtime_run(test_db, user, kind="assistant_turn", engine="pi")
    token = create_pi_bridge_token(run=parent, user=user)

    try:
        execute_pi_tool(
            PiBridgeToolCall(
                run_id="another-run",
                tool_call_id="delegate-2",
                name="spawn_subagents",
                arguments={"mode": "single", "task": "不应执行"},
            ),
            authorization=f"Bearer {token}",
        )
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("run scope mismatch was not rejected")
