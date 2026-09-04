"""Public API schemas for runtime runs and replayable events."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from contracts.runtime import RuntimeApprovalDecisionType


class RuntimeLinkedWorkflowRun(BaseModel):
    """A durable LangGraph workflow child of an assistant RuntimeRun."""

    id: str
    status: str
    project_id: str | None = None
    execution_run_id: str | None = None
    engine: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RuntimeRunRead(BaseModel):
    id: str
    kind: str
    status: str
    project_id: str | None = None
    conversation_id: str | None = None
    execution_run_id: str | None = None
    engine: str
    trace_id: str
    parent_run_id: str | None = None
    linked_workflow_runs: list[RuntimeLinkedWorkflowRun] = Field(default_factory=list)


class RuntimeRunListItem(BaseModel):
    """Safe aggregate RuntimeRun data for the user-facing Run Center."""

    id: str
    kind: str
    status: str
    project_id: str | None = None
    conversation_id: str | None = None
    project_name: str | None = None
    engine: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    latest_event_summary: str | None = None
    parent_run_id: str | None = None


class RuntimeChildRunRead(BaseModel):
    """A safe child-run projection for nested user-facing timelines."""

    id: str
    parent_run_id: str
    kind: str
    status: str
    profile: str | None = None
    mode: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    latest_event_summary: str | None = None


class RuntimeEventRead(BaseModel):
    event_id: str
    run_id: str
    parent_event_id: str | None = None
    sequence: int
    type: str
    public_summary: str
    payload: dict = Field(default_factory=dict)
    schema_version: str
    timestamp: datetime


class RuntimeEventsResponse(BaseModel):
    items: list[RuntimeEventRead]


class RuntimeApprovalResolveRequest(BaseModel):
    decision: RuntimeApprovalDecisionType
    edited_arguments: dict | None = None


class RuntimeActionResolutionRead(BaseModel):
    action_id: str
    status: str
    public_summary: str | None = None
    approval_status: str | None = None


class RuntimeDiagnosticTimingRead(BaseModel):
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)


class RuntimeDiagnosticRetryRead(BaseModel):
    execution_retries: int = Field(default=0, ge=0)
    provider_retries: int = Field(default=0, ge=0)
    task_redeliveries: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)


class RuntimeDiagnosticActionRead(BaseModel):
    action_id: str
    capability: str
    status: str
    risk_level: str
    policy_outcome: str
    approval_mode: str
    public_summary: str | None = None
    error_code: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)


class RuntimeDiagnosticApprovalRead(BaseModel):
    approval_id: str
    action_id: str
    capability: str
    status: str
    decision: str | None = None
    created_at: datetime
    expires_at: datetime
    resolved_at: datetime | None = None
    wait_duration_ms: int = Field(ge=0)


class RuntimeDiagnosticEventRead(BaseModel):
    event_id: str
    run_id: str
    sequence: int
    type: str
    public_summary: str
    timestamp: datetime


class RuntimeDiagnosticExecutionRunRead(BaseModel):
    execution_run_id: str
    parent_execution_run_id: str | None = None
    run_type: str
    status: str
    attempt_number: int = Field(ge=1)
    timing: RuntimeDiagnosticTimingRead


class RuntimeDiagnosticWorkerTaskRead(BaseModel):
    task_name: str
    status: str
    dispatch_attempts: int = Field(ge=0)
    delivery_attempts: int = Field(ge=0)
    last_error_code: str | None = None
    created_at: datetime
    dispatched_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)


class RuntimeDiagnosticModelUsageRead(BaseModel):
    provider_source: str
    provider_type: str
    model_name: str
    workload: str
    call_count: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    reasoning_tokens: int = Field(ge=0)
    cache_read_tokens: int = Field(ge=0)
    cache_write_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cost_status: str
    cost_amount_micros: int | None = Field(default=None, ge=0)
    cost_currency: str | None = None


class RuntimeDiagnosticRetrievalRead(BaseModel):
    retrieval_attempt_count: int = Field(ge=0)
    candidate_count: int | None = Field(default=None, ge=0)
    fused_candidate_count: int | None = Field(default=None, ge=0)
    reranked_candidate_count: int | None = Field(default=None, ge=0)
    evidence_hit_count: int | None = Field(default=None, ge=0)
    evidence_set_count: int = Field(ge=0)
    retrieval_latency_ms: int | None = Field(default=None, ge=0)
    degraded_evidence_set_count: int = Field(ge=0)


class RuntimeDiagnosticAuditEventRead(BaseModel):
    event_id: str
    event_type: str
    created_at: datetime | None = None


class RuntimeDiagnosticDeliverableRead(BaseModel):
    deliverable_id: str
    deliverable_title: str
    deliverable_status: str
    section_version_id: str
    section_key: str
    section_title: str
    section_status: str
    version_number: int = Field(ge=1)


class RuntimeDiagnosticsRead(BaseModel):
    """Redacted, administrator-only diagnostic view for one durable run trace."""

    run_id: str
    trace_id: str
    request_ref: str | None = None
    user_ref: str | None = None
    org_ref: str | None = None
    kind: str
    status: str
    engine: str
    project_id: str | None = None
    conversation_id: str | None = None
    execution_run_id: str | None = None
    parent_run_id: str | None = None
    model: str | None = None
    reasoning_effort: str | None = None
    provider_source: str
    timing: RuntimeDiagnosticTimingRead
    error_code: str | None = None
    failure_category: str | None = None
    cancellation_requested: bool
    retries: RuntimeDiagnosticRetryRead
    approval_wait_duration_ms: int = Field(ge=0)
    actions: list[RuntimeDiagnosticActionRead] = Field(default_factory=list)
    approvals: list[RuntimeDiagnosticApprovalRead] = Field(default_factory=list)
    event_count: int = Field(ge=0)
    events_truncated: bool = False
    events: list[RuntimeDiagnosticEventRead] = Field(default_factory=list)
    execution_runs: list[RuntimeDiagnosticExecutionRunRead] = Field(default_factory=list)
    worker_tasks: list[RuntimeDiagnosticWorkerTaskRead] = Field(default_factory=list)
    model_usage: list[RuntimeDiagnosticModelUsageRead] = Field(default_factory=list)
    cost_status: str
    retrieval: RuntimeDiagnosticRetrievalRead
    audit_events: list[RuntimeDiagnosticAuditEventRead] = Field(default_factory=list)
    deliverables: list[RuntimeDiagnosticDeliverableRead] = Field(default_factory=list)
    alert_codes: list[str] = Field(default_factory=list)
