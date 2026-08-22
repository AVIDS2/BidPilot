"""Safety policies for assistant tool execution."""

from __future__ import annotations

from app.runtime.policy import ApprovalMode, tool_requires_approval


def requires_confirmation(tool_name: str, approval_mode: ApprovalMode = "risky_only") -> bool:
    return tool_requires_approval(tool_name, approval_mode)
