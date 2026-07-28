from typing import Literal

from pydantic import BaseModel, Field

ReasoningEffort = Literal["low", "medium", "high", "extra", "max", "ultra"]


class DraftSectionRequest(BaseModel):
    project_id: str
    section_key: str
    provider_config_id: str | None = None
    reasoning_effort: ReasoningEffort | None = None
    parent_runtime_run_id: str | None = None


class RedraftSectionRequest(BaseModel):
    project_id: str
    section_key: str
    review_feedback: str | None = Field(default=None, max_length=4_000)
    provider_config_id: str | None = None
    reasoning_effort: ReasoningEffort | None = None
    parent_runtime_run_id: str | None = None


class DraftSectionResponse(BaseModel):
    run_id: str
    status: str
    runtime_run_id: str | None = None


class ResumeRunRequest(BaseModel):
    """Payload to resume an interrupted LangGraph drafting run.

    Sent to ``POST /drafting/runs/{run_id}/resume`` when a human reviewer
    has made a decision on the AI-generated draft.
    """

    decision: Literal["approved", "rejected"]
    feedback: str | None = Field(default=None, max_length=4_000)


# ── SSE event schemas ────────────────────────────────────────────────────
# These models document the shape of each SSE event emitted by
# ``GET /drafting/runs/{run_id}/stream``.  They are not enforced at
# runtime (SSE data is JSON-serialized dict) but serve as a typed
# contract for frontend consumers and tests.


class SSEConnectedEvent(BaseModel):
    """Emitted when the SSE stream is first established."""

    run_id: str
    status: str
    timestamp: str


class SSENodeStartedEvent(BaseModel):
    """Emitted when a graph node begins executing."""

    node_name: str
    timestamp: str


class SSENodeCompletedEvent(BaseModel):
    """Emitted when a graph node finishes execution."""

    node_name: str
    result_summary: str
    timestamp: str


class SSEReviewResultEvent(BaseModel):
    """Emitted after the quality reviewer node completes."""

    passed: bool
    issues: list[str]
    score: float


class SSEHumanApprovalRequiredEvent(BaseModel):
    """Emitted when the graph pauses for human-in-the-loop review."""

    draft_preview: str
    review_score: float | None = None
    section_version_id: str | None = None
    timestamp: str


class SSEGraphCompletedEvent(BaseModel):
    """Emitted when the graph finishes successfully."""

    persisted: bool
    section_version_id: str | None = None
    status: str
    timestamp: str


class SSEGraphErrorEvent(BaseModel):
    """Emitted when an error occurs during graph execution."""

    error_message: str
    timestamp: str | None = None


class SSEGraphCancelledEvent(BaseModel):
    """Emitted when a workflow stops at a durable cancellation boundary."""

    status: Literal["cancelled"]
    timestamp: str


class SSEHeartbeatEvent(BaseModel):
    """Periodic status update emitted during fallback polling."""

    run_id: str
    status: str
    elapsed_seconds: float
    timestamp: str
