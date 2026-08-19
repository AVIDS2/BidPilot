from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.auth.schemas import CurrentUser
from app.models import Project, RuntimeRun, User
from app.runtime.assistant_adapter import _render_runtime_event
from app.runtime.events import RuntimeEventDraft, list_events_after, publish_event
from app.runtime.repository import get_visible_runtime_run
from contracts.runtime import RuntimeEventType


def _current_user(default_org_id: str, default_user_id: str) -> CurrentUser:
    return CurrentUser(
        id=default_user_id,
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=default_org_id,
    )


def _runtime_run(test_db, default_org_id: str, default_user_id: str) -> RuntimeRun:
    run = RuntimeRun(
        kind="assistant_turn",
        status="running",
        org_id=default_org_id,
        user_id=default_user_id,
        engine="deterministic",
        trace_id=f"trace-{uuid.uuid4().hex}",
        policy_snapshot_json={"approval_mode": "risky_only"},
    )
    test_db.add(run)
    test_db.commit()
    test_db.refresh(run)
    return run


def test_publish_allocates_contiguous_sequences_and_redacts_payload(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    run = _runtime_run(test_db, default_org_id, default_user_id)

    first = publish_event(
        test_db,
        run.id,
        RuntimeEventDraft(type=RuntimeEventType.RUN_STARTED, public_summary="任务已开始。"),
    )
    second = publish_event(
        test_db,
        run.id,
        RuntimeEventDraft(
            type=RuntimeEventType.CAPABILITY_STARTED,
            public_summary="正在搜索项目。",
            payload={"api_key": "test-secret-should-never-persist", "query": "示例"},
        ),
    )

    assert (first.sequence, second.sequence) == (1, 2)
    assert second.payload_json == {"api_key": "***redacted***", "query": "示例"}
    assert [event.sequence for event in list_events_after(test_db, run.id, after_sequence=1)] == [2]


def test_publish_normalizes_non_json_capability_values(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    run = _runtime_run(test_db, default_org_id, default_user_id)
    observed_at = datetime(2026, 8, 8, 13, 42, 45, tzinfo=UTC)
    source_id = uuid.uuid4()

    event = publish_event(
        test_db,
        run.id,
        RuntimeEventDraft(
            type=RuntimeEventType.CAPABILITY_SUCCEEDED,
            public_summary="需求已读取。",
            payload={
                "observed_at": observed_at,
                "source_id": source_id,
                "score": Decimal("12.50"),
                "binary": b"not-for-json",
            },
        ),
    )

    assert event.payload_json == {
        "observed_at": observed_at.isoformat(),
        "source_id": str(source_id),
        "score": "12.50",
        "binary": "<binary:12 bytes>",
    }


def test_publish_persists_provider_reasoning_as_a_replayable_event(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    run = _runtime_run(test_db, default_org_id, default_user_id)

    event = publish_event(
        test_db,
        run.id,
        RuntimeEventDraft(
            type=RuntimeEventType.REASONING_DELTA,
            public_summary="先检查现有项目，再决定下一步。",
            payload={"turn_id": "turn-1", "source": "provider", "api_key": "test-secret-never-store"},
        ),
    )

    assert event.event_type == RuntimeEventType.REASONING_DELTA.value
    assert event.schema_version == "1.2"
    assert event.payload_json == {
        "turn_id": "turn-1",
        "source": "provider",
        "api_key": "***redacted***",
    }


def test_provider_reasoning_event_is_not_exposed_to_the_sse_stream() -> None:
    event = SimpleNamespace(
        id="event-1",
        run_id="run-1",
        parent_event_id="turn-event-1",
        sequence=3,
        event_type=RuntimeEventType.REASONING_DELTA.value,
        public_summary="先读取项目资料。",
        payload_json={"turn_id": "turn-1", "source": "provider", "chunk_index": 0},
        created_at=datetime.now(UTC),
    )

    rendered = _render_runtime_event(event, "conversation-1")

    assert rendered == []


def test_project_runtime_run_is_hidden_from_non_member(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    project = Project(
        slug=f"runtime-private-{uuid.uuid4().hex[:8]}",
        name="Runtime Private Project",
        scenario_package="bidpilot",
        org_id=default_org_id,
    )
    other_user = User(
        id=f"runtime-member-{uuid.uuid4().hex[:8]}",
        org_id=default_org_id,
        email=f"runtime-member-{uuid.uuid4().hex[:8]}@example.test",
        display_name="Runtime Member",
        role="member",
        password_hash="test-only",
    )
    test_db.add_all([project, other_user])
    test_db.flush()
    run = RuntimeRun(
        kind="assistant_turn",
        status="running",
        org_id=default_org_id,
        user_id=default_user_id,
        project_id=project.id,
        engine="deterministic",
        trace_id=f"trace-{uuid.uuid4().hex}",
        policy_snapshot_json={"approval_mode": "risky_only"},
    )
    test_db.add(run)
    test_db.commit()

    with pytest.raises(HTTPException) as exc_info:
        get_visible_runtime_run(
            test_db,
            run.id,
            CurrentUser(
                id=other_user.id,
                email=other_user.email,
                display_name=other_user.display_name,
                role="member",
                org_id=default_org_id,
            ),
        )

    assert exc_info.value.status_code == 404


def test_runtime_event_api_replays_only_events_after_cursor(
    client,
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    run = _runtime_run(test_db, default_org_id, default_user_id)
    second = publish_event(
        test_db,
        run.id,
        RuntimeEventDraft(type=RuntimeEventType.RUN_STARTED, public_summary="任务已开始。"),
    )
    second = publish_event(
        test_db,
        run.id,
        RuntimeEventDraft(
            type=RuntimeEventType.CAPABILITY_SUCCEEDED,
            public_summary="已找到 2 个项目。",
            payload={"count": 2},
        ),
    )

    response = client.get(f"/runtime/runs/{run.id}/events?after_sequence=1")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "event_id": second.id,
                "run_id": run.id,
                "parent_event_id": None,
                "sequence": 2,
                "type": "capability.succeeded",
                "public_summary": "已找到 2 个项目。",
                "payload": {"count": 2},
                "schema_version": "1.2",
                "timestamp": second.created_at.isoformat(),
            }
        ]
    }
