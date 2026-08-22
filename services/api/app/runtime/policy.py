"""Server-side runtime policy evaluation for registered capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.runtime import RuntimePolicyDecision, RuntimePolicyOutcome, RuntimeRiskLevel

from .registry import CapabilityDefinition
from .registry import CAPABILITY_REGISTRY, get_capability_definition


ApprovalMode = Literal["request_approval", "risky_only", "full_access", "custom"]

RiskLevel = Literal["read", "navigate", "low_risk_write", "costing", "destructive"]


@dataclass(frozen=True)
class ToolPolicy:
    """Stable, user-facing policy metadata derived from the capability registry."""

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


def evaluate_policy(definition: CapabilityDefinition, *, approval_mode: ApprovalMode) -> RuntimePolicyDecision:
    if approval_mode not in {"request_approval", "risky_only", "full_access", "custom"}:
        raise ValueError(f"Invalid approval mode: {approval_mode}")

    if definition.risk_level is RuntimeRiskLevel.DESTRUCTIVE or definition.requires_typed_confirmation:
        return _approval_decision(definition, "destructive_action")

    if approval_mode == "full_access":
        return _allow_decision(definition, "full_access")

    if approval_mode in {"request_approval", "custom"} and definition.risk_level not in {
        RuntimeRiskLevel.READ,
        RuntimeRiskLevel.NAVIGATE,
    }:
        return _approval_decision(definition, "approval_mode")

    if definition.requires_approval_in_risky_only:
        return _approval_decision(definition, "capability_policy")

    return _allow_decision(definition, "safe_capability")


def _allow_decision(definition: CapabilityDefinition, reason_code: str) -> RuntimePolicyDecision:
    return RuntimePolicyDecision(
        outcome=RuntimePolicyOutcome.ALLOW,
        risk_level=definition.risk_level,
        reason_code=reason_code,
        public_message="该操作可以直接执行。",
        requires_typed_confirmation=False,
    )


def _approval_decision(definition: CapabilityDefinition, reason_code: str) -> RuntimePolicyDecision:
    return RuntimePolicyDecision(
        outcome=RuntimePolicyOutcome.REQUIRE_APPROVAL,
        risk_level=definition.risk_level,
        reason_code=reason_code,
        public_message="该操作需要你的确认。",
        requires_typed_confirmation=definition.requires_typed_confirmation,
    )
