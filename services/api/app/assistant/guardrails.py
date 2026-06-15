"""Safety policies for assistant tool execution."""

from __future__ import annotations

CONFIRMATION_REQUIRED_TOOLS = {
    "create_project",
    "start_draft_section",
    "start_redraft_section",
}


def requires_confirmation(tool_name: str) -> bool:
    return tool_name in CONFIRMATION_REQUIRED_TOOLS
