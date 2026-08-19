"""Pure Pi runtime mappings shared by API and Worker processes."""

from __future__ import annotations


def pi_thinking_level(reasoning_effort: str | None) -> str:
    return {
        None: "off",
        "low": "low",
        "medium": "medium",
        "high": "high",
        "extra": "high",
        "max": "xhigh",
    }.get(reasoning_effort, "off")


def pi_model_api(provider_type: str, provider_id: str | None) -> str:
    value = f"{provider_type} {provider_id or ''}".casefold()
    return "anthropic-messages" if "anthropic" in value else "openai-completions"


__all__ = ["pi_model_api", "pi_thinking_level"]
