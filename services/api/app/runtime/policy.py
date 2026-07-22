"""Server-side runtime policy evaluation for registered capabilities."""

from __future__ import annotations

from typing import Literal

from contracts.runtime import RuntimePolicyDecision, RuntimePolicyOutcome, RuntimeRiskLevel

from .registry import CapabilityDefinition


ApprovalMode = Literal["request_approval", "risky_only", "full_access", "custom"]


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
