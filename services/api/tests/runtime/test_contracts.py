from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.runtime import (
    RuntimeActionStatus,
    RuntimeApprovalDecision,
    RuntimeApprovalStatus,
    RuntimeEventRecord,
    RuntimeEventType,
)


def test_runtime_event_requires_a_monotonic_sequence_and_public_summary() -> None:
    event = RuntimeEventRecord(
        run_id="run-1",
        sequence=2,
        type=RuntimeEventType.CAPABILITY_SUCCEEDED,
        public_summary="已找到 2 个项目。",
        payload={"count": 2},
    )

    assert event.sequence == 2
    assert event.payload["count"] == 2

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
