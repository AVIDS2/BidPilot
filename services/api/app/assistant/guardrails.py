"""Safety policies for assistant tool execution."""

from __future__ import annotations

CONFIRMATION_REQUIRED_TOOLS = {
    "create_project",
    "start_draft_section",
    "start_redraft_section",
    "create_deliverable",
    "retry_run",
    "delete_project",
}


def requires_confirmation(tool_name: str) -> bool:
    return tool_name in CONFIRMATION_REQUIRED_TOOLS
