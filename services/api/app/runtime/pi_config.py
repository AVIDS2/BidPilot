"""Server-owned Pi tools, resources and cloud sandbox configuration."""

from __future__ import annotations

from typing import Any

from contracts.runtime import RuntimeRiskLevel

from .registry import CAPABILITY_REGISTRY
from .skills import build_skill_index
from .tool_catalog import (
    _READ_SKILL_TOOL_SPEC,
    _TOOL_PARAMETER_SCHEMAS,
    build_capability_tool_specs,
)


def pi_tools() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for spec in [*build_capability_tool_specs(), _READ_SKILL_TOOL_SPEC]:
        function = spec.get("function") if isinstance(spec, dict) else None
        if not isinstance(function, dict):
            continue
        name = str(function.get("name") or "")
        if not name:
            continue
        definition = CAPABILITY_REGISTRY.get(name)
        read_only = definition is not None and definition.risk_level is RuntimeRiskLevel.READ
        result.append(
            {
                "name": name,
                "label": (definition.label_zh if definition else name),
                "description": str(function.get("description") or name),
                "parameters": function.get("parameters") or _TOOL_PARAMETER_SCHEMAS.get(name, {}),
                "executionMode": "parallel" if read_only else "sequential",
            }
        )
    return result


def pi_resources() -> dict[str, Any]:
    """Trusted Pi resources selected by the server, never by browser input."""
    return {
        "extensions": ["bidpilot-governance", "bidpilot-skills", "bidpilot-subagents"],
        "skills": [
            {"name": skill.name, "description": skill.description}
            for skill in build_skill_index()
        ],
    }


def pi_sandbox() -> dict[str, Any]:
    """Cloud Pi is capability-only; business approval never grants host access."""
    return {
        "profile": "governed_cloud",
        "hostTools": "disabled",
        "network": "bridge_only",
        "maxToolInputBytes": 128 * 1024,
        "maxToolObservationBytes": 512 * 1024,
    }


def pi_execution_contract() -> dict[str, Any]:
    """Freeze the audited child capability surface at delegation time."""
    return {
        "version": "1",
        "tools": pi_tools(),
        "resources": pi_resources(),
        "sandbox": pi_sandbox(),
    }


__all__ = ["pi_execution_contract", "pi_resources", "pi_sandbox", "pi_tools"]
