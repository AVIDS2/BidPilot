"""Compatibility projection of runtime capability policy metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.runtime.policy import evaluate_policy
from app.runtime.registry import CAPABILITY_REGISTRY, get_capability_definition


RiskLevel = Literal["read", "navigate", "low_risk_write", "costing", "destructive"]
ApprovalMode = Literal["request_approval", "risky_only", "full_access", "custom"]


@dataclass(frozen=True)
class ToolPolicy:
    name: str
    label_zh: str
    label_en: str
    risk_level: RiskLevel
    requires_approval: bool = False
    requires_typed_confirmation: bool = False


TOOL_POLICIES: dict[str, ToolPolicy] = {
    definition.name: ToolPolicy(
        name=definition.name,
        label_zh=definition.label_zh,
        label_en=definition.label_en,
        risk_level=definition.risk_level.value,  # type: ignore[arg-type]
        requires_approval=definition.requires_approval_in_risky_only,
        requires_typed_confirmation=definition.requires_typed_confirmation,
    )
    for definition in CAPABILITY_REGISTRY.values()
}


def get_tool_policy(tool_name: str) -> ToolPolicy | None:
    return TOOL_POLICIES.get(tool_name)


def tool_requires_approval(tool_name: str, approval_mode: ApprovalMode = "risky_only") -> bool:
    try:
        definition = get_capability_definition(tool_name)
    except ValueError:
        return True
    return evaluate_policy(definition, approval_mode=approval_mode).requires_approval
