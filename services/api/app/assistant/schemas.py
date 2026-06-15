"""Schemas for the product-native assistant harness."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


AssistantMode = Literal["answer", "needs_input", "tool_action", "workflow_trigger"]
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


class AssistantRequest(BaseModel):
    message: str
    project_id: str | None = None
    conversation_id: str | None = None
    provider_config_id: str | None = None
    confirmation: AssistantConfirmation | None = None


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
