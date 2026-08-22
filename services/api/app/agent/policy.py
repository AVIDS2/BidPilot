"""Compatibility exports for the retired ``app.agent`` namespace.

New API code imports policy from ``app.runtime.policy``.  This module remains
only so historical tests and replay fixtures do not break while the old agent
package is being retired.
"""

from __future__ import annotations

from app.runtime.policy import (
    ApprovalMode,
    RiskLevel,
    TOOL_POLICIES,
    ToolPolicy,
    get_tool_policy,
    tool_requires_approval,
)

__all__ = [
    "ApprovalMode",
    "RiskLevel",
    "TOOL_POLICIES",
    "ToolPolicy",
    "get_tool_policy",
    "tool_requires_approval",
]
