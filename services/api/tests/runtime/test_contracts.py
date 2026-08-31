from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.runtime import (
    RUNTIME_EVENT_SCHEMA_VERSION,
    RuntimeActionStatus,
    RuntimeApprovalDecision,
    RuntimeApprovalStatus,
    RuntimeEventRecord,
    RuntimeEventType,
)


def test_runtime_event_requires_a_monotonic_sequence_and_public_summary() -> None:
    long_summary = "完整回答" * 800
    event = RuntimeEventRecord(
        run_id="run-1",
        sequence=2,
        type=RuntimeEventType.CAPABILITY_SUCCEEDED,
        public_summary=long_summary,
        payload={"count": 2},
    )

    assert event.sequence == 2
    assert event.payload["count"] == 2
    assert event.public_summary == long_summary
    assert event.event_id
    assert event.schema_version == "1.2"
    assert RUNTIME_EVENT_SCHEMA_VERSION == "1.2"

    with pytest.raises(ValidationError):
        RuntimeEventRecord(
            run_id="run-1",
            sequence=0,
            type=RuntimeEventType.CAPABILITY_SUCCEEDED,
            public_summary="完成",
        )


def test_runtime_approval_cannot_be_pending_after_a_terminal_action() -> None:
    with pytest.raises(ValidationError, match="pending approval requires an action awaiting approval"):
        RuntimeApprovalDecision(
            action_status=RuntimeActionStatus.SUCCEEDED,
            status=RuntimeApprovalStatus.PENDING,
        )

    approval = RuntimeApprovalDecision(
        action_status=RuntimeActionStatus.AWAITING_APPROVAL,
        status=RuntimeApprovalStatus.PENDING,
    )
    assert approval.status is RuntimeApprovalStatus.PENDING
