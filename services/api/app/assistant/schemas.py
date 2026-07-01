"""Schemas for the product-native assistant harness."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


AssistantMode = Literal["answer", "needs_input", "tool_action", "workflow_trigger"]
AssistantAttachmentKind = Literal["file", "image"]
AssistantAttachmentStatus = Literal["extracted", "empty", "unsupported", "failed"]
AssistantReasoningEffort = Literal["low", "medium", "high", "ultra", "max"]
AssistantState = Literal[
    "idle",
    "thinking",
    "needs_input",
    "needs_confirmation",
    "executing_tool",
    "running_workflow",
    "completed",
    "failed",
]


class AssistantConfirmation(BaseModel):
    approved: bool
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class AssistantAttachmentPayload(BaseModel):
    id: str | None = None
    name: str
    kind: AssistantAttachmentKind = "file"
    mime_type: str | None = None
    size: int | None = None
    extraction_status: AssistantAttachmentStatus | None = None
    extracted_text: str | None = None
    document_id: str | None = None
    error: str | None = None


class AssistantAttachmentUploadResponse(BaseModel):
    id: str
    name: str
    kind: AssistantAttachmentKind
    mime_type: str
    size: int
    extraction_status: AssistantAttachmentStatus
    extracted_text: str = ""
    error: str | None = None


class AssistantRequest(BaseModel):
    message: str
    project_id: str | None = None
    conversation_id: str | None = None
    provider_config_id: str | None = None
    reasoning_effort: AssistantReasoningEffort | None = None
    confirmation: AssistantConfirmation | None = None
    attachments: list[AssistantAttachmentPayload] = Field(default_factory=list)


class AssistantIntent(BaseModel):
    mode: AssistantMode
    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    response: str | None = None


class AssistantEvent(BaseModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class AssistantToolResult(BaseModel):
    tool_name: str
    result: dict[str, Any]
    summary: str
    workflow: bool = False
