"""Framework-neutral contracts for BidPilot's governed runtime."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RuntimeRunKind(StrEnum):
    ASSISTANT_TURN = "assistant_turn"
    WORKFLOW_BRIDGE = "workflow_bridge"
    SYSTEM_RECOVERY = "system_recovery"


class RuntimeRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class RuntimeActionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class RuntimeApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class RuntimeApprovalDecisionType(StrEnum):
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"


class RuntimePolicyOutcome(StrEnum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


class RuntimeRiskLevel(StrEnum):
    READ = "read"
    NAVIGATE = "navigate"
    LOW_RISK_WRITE = "low_risk_write"
    COSTING = "costing"
    DESTRUCTIVE = "destructive"


class RuntimeEventType(StrEnum):
    RUN_STARTED = "run.started"
    PLAN_PROPOSED = "plan.proposed"
    PLAN_UPDATED = "plan.updated"
    CAPABILITY_STARTED = "capability.started"
    CAPABILITY_PROGRESSED = "capability.progressed"
    CAPABILITY_SUCCEEDED = "capability.succeeded"
    CAPABILITY_FAILED = "capability.failed"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_RESOLVED = "approval.resolved"
    WORKFLOW_LINKED = "workflow.linked"
    MESSAGE_DELTA = "message.delta"
    MESSAGE_COMPLETED = "message.completed"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_CANCELLED = "run.cancelled"


class _RuntimeContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RuntimeContext(_RuntimeContract):
    run_id: str = Field(min_length=1, max_length=36)
    trace_id: str = Field(min_length=1, max_length=100)
    user_id: str = Field(min_length=1, max_length=36)
    org_id: str = Field(min_length=1, max_length=36)
    project_id: str | None = Field(default=None, max_length=36)
    conversation_id: str | None = Field(default=None, max_length=36)
    execution_run_id: str | None = Field(default=None, max_length=36)
    parent_run_id: str | None = Field(default=None, max_length=36)
    engine: str = Field(min_length=1, max_length=80)
    approval_mode: Literal["request_approval", "risky_only", "full_access", "custom"] = "risky_only"
    provider_config_id: str | None = Field(default=None, max_length=36)
    model: str | None = Field(default=None, max_length=255)
    reasoning_effort: Literal["low", "medium", "high", "extra", "max"] | None = None
    idempotency_key: str | None = Field(default=None, max_length=255)
    allowed_project_ids: list[str] = Field(default_factory=list)
    allow_network: bool = False


class RuntimePolicyDecision(_RuntimeContract):
    outcome: RuntimePolicyOutcome
    risk_level: RuntimeRiskLevel
    reason_code: str = Field(min_length=1, max_length=100)
    public_message: str = Field(min_length=1, max_length=500)
    requires_typed_confirmation: bool = False

    @property
    def requires_approval(self) -> bool:
        return self.outcome is RuntimePolicyOutcome.REQUIRE_APPROVAL


class RuntimeEventRecord(_RuntimeContract):
    event_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=36)
    run_id: str = Field(min_length=1, max_length=36)
    parent_event_id: str | None = Field(default=None, min_length=1, max_length=36)
    sequence: int = Field(ge=1)
    type: RuntimeEventType
    public_summary: str = Field(min_length=1, max_length=2000)
    payload: dict[str, Any] = Field(default_factory=dict)
    schema_version: Literal["1.0", "1.1"] = "1.1"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RuntimeApprovalDecision(_RuntimeContract):
    action_status: RuntimeActionStatus
    status: RuntimeApprovalStatus
    decision: RuntimeApprovalDecisionType | None = None
    edited_arguments: dict[str, Any] | None = None
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_action_and_approval_state(self) -> RuntimeApprovalDecision:
        if self.status is RuntimeApprovalStatus.PENDING:
            if self.action_status is not RuntimeActionStatus.AWAITING_APPROVAL:
                raise ValueError("pending approval requires an action awaiting approval")
            if self.decision is not None:
                raise ValueError("pending approval cannot include a decision")
        if self.status is RuntimeApprovalStatus.APPROVED and self.decision is not RuntimeApprovalDecisionType.APPROVE:
            raise ValueError("approved status requires an approve decision")
        if self.status is RuntimeApprovalStatus.EDITED:
            if self.decision is not RuntimeApprovalDecisionType.EDIT or self.edited_arguments is None:
                raise ValueError("edited status requires an edit decision and edited arguments")
        if self.status is RuntimeApprovalStatus.REJECTED and self.decision is not RuntimeApprovalDecisionType.REJECT:
            raise ValueError("rejected status requires a reject decision")
        return self


__all__ = [
    "RuntimeActionStatus",
    "RuntimeApprovalDecision",
    "RuntimeApprovalDecisionType",
    "RuntimeApprovalStatus",
    "RuntimeContext",
    "RuntimeEventRecord",
    "RuntimeEventType",
    "RuntimePolicyDecision",
    "RuntimePolicyOutcome",
    "RuntimeRiskLevel",
    "RuntimeRunKind",
    "RuntimeRunStatus",
]
