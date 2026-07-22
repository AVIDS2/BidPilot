"""Provider-neutral, redacted model-usage measurements.

The adapters pass only numeric usage counters across this boundary. Prompts,
completions, API keys, base URLs, and raw provider payloads never belong in a
usage ledger.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


def _non_negative_int(value: object) -> int:
    """Normalize a provider usage value without trusting its wire type."""
    if isinstance(value, bool):
        return 0
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


@dataclass(frozen=True)
class ProviderUsageMeasurement:
    """A provider-reported token measurement for one successful invocation."""

    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reported_total_tokens: int | None = None

    @property
    def total_tokens(self) -> int:
        if self.reported_total_tokens is not None:
            return max(self.reported_total_tokens, 0)
        return (
            self.input_tokens
            + self.output_tokens
            + self.reasoning_tokens
            + self.cache_read_tokens
            + self.cache_write_tokens
        )


def normalize_openai_usage(response: Mapping[str, Any]) -> ProviderUsageMeasurement | None:
    """Read the documented OpenAI-compatible chat-completions usage shape."""
    usage = _mapping(response.get("usage"))
    if not usage:
        return None
    detail = _mapping(usage.get("completion_tokens_details"))
    prompt_detail = _mapping(usage.get("prompt_tokens_details"))
    recognized = {
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    }
    if not any(key in usage for key in recognized):
        return None
    return ProviderUsageMeasurement(
        input_tokens=_non_negative_int(usage.get("prompt_tokens")),
        output_tokens=_non_negative_int(usage.get("completion_tokens")),
        reasoning_tokens=_non_negative_int(detail.get("reasoning_tokens")),
        cache_read_tokens=_non_negative_int(prompt_detail.get("cached_tokens")),
        reported_total_tokens=(
            _non_negative_int(usage.get("total_tokens"))
            if "total_tokens" in usage
            else None
        ),
    )


def normalize_anthropic_usage(response: Mapping[str, Any]) -> ProviderUsageMeasurement | None:
    """Read the documented Anthropic Messages API usage shape."""
    usage = _mapping(response.get("usage"))
    if not usage:
        return None
    recognized = {
        "input_tokens",
        "output_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
    }
    if not any(key in usage for key in recognized):
        return None
    return ProviderUsageMeasurement(
        input_tokens=_non_negative_int(usage.get("input_tokens")),
        output_tokens=_non_negative_int(usage.get("output_tokens")),
        cache_read_tokens=_non_negative_int(usage.get("cache_read_input_tokens")),
        cache_write_tokens=_non_negative_int(usage.get("cache_creation_input_tokens")),
    )


def normalize_langchain_usage(metadata: object) -> ProviderUsageMeasurement | None:
    """Normalize LangChain's provider-agnostic AIMessage usage metadata."""
    usage = _mapping(metadata)
    if not usage:
        return None
    input_detail = _mapping(usage.get("input_token_details"))
    output_detail = _mapping(usage.get("output_token_details"))
    recognized = {"input_tokens", "output_tokens", "total_tokens"}
    if not any(key in usage for key in recognized):
        return None
    return ProviderUsageMeasurement(
        input_tokens=_non_negative_int(usage.get("input_tokens")),
        output_tokens=_non_negative_int(usage.get("output_tokens")),
        reasoning_tokens=_non_negative_int(output_detail.get("reasoning")),
        cache_read_tokens=_non_negative_int(input_detail.get("cache_read")),
        cache_write_tokens=_non_negative_int(input_detail.get("cache_creation")),
        reported_total_tokens=(
            _non_negative_int(usage.get("total_tokens"))
            if "total_tokens" in usage
            else None
        ),
    )
