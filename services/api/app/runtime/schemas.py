"""Public API schemas for runtime runs and replayable events."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from contracts.runtime import RuntimeApprovalDecisionType


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


class RuntimeRunListItem(BaseModel):
    """Safe aggregate RuntimeRun data for the user-facing Run Center."""

    id: str
    kind: str
    status: str
    project_id: str | None = None
    project_name: str | None = None
    engine: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    latest_event_summary: str | None = None


class RuntimeEventRead(BaseModel):
    run_id: str
    sequence: int
    type: str
    public_summary: str
    payload: dict = Field(default_factory=dict)
    schema_version: str


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
