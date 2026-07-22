"""Bounded provider-neutral structured-text calls for workflow nodes."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.adapters.anthropic_llm import (
    _ADAPTIVE_THINKING_EFFORT,
    _THINKING_BUDGETS,
    _api_key as anthropic_api_key,
    _api_model as anthropic_api_model,
    _api_url as anthropic_api_url,
    _supports_adaptive_thinking,
    _supports_thinking,
)
from app.adapters.llm import (
    _OPENAI_REASONING_EFFORT,
    _api_key as openai_api_key,
    _api_model as openai_api_model,
    _api_url as openai_api_url,
    _supports_reasoning_effort,
)
from app.adapters.provider_errors import ProviderInvocationError, provider_error_for_status
from app.provider_registry import get_provider_by_id
from contracts.model_usage import (
    ProviderUsageMeasurement,
    normalize_anthropic_usage,
    normalize_openai_usage,
)
from contracts.provider_profiles import ProviderProfileError, resolve_provider_chat_request
from contracts.untrusted_context import with_untrusted_context_guard


_MAX_SYSTEM_PROMPT_CHARACTERS = 4_000
_MAX_USER_PROMPT_CHARACTERS = 16_000
_MAX_OUTPUT_TOKENS = 4_096


@dataclass(frozen=True)
class StructuredModelResult:
    """A provider response with only content, model identity, and token use."""

    content: str
    model_used: str
    provider_type: str
    usage: ProviderUsageMeasurement | None


def resolve_structured_provider(
    provider_config_id: str | None,
) -> tuple[dict[str, str | None] | None, str]:
    """Resolve the already-authorized workflow provider without fallback."""
    if not provider_config_id:
        return None, "openai"
    provider = get_provider_by_id(provider_config_id)
    if provider is None:
        raise ProviderInvocationError(
            "provider_config_missing",
            "所选模型提供商配置已不可用，请重新选择后再试。",
            retryable=False,
        )
    return (
        {
            "api_key": provider.api_key,
            "api_url": provider.api_url,
            "model": provider.model,
            "provider_id": provider.provider_id,
        },
        provider.provider_type,
    )


def _bounded_output_tokens(value: int) -> int:
    return max(1, min(value, _MAX_OUTPUT_TOKENS))


def _openai_connection(
    provider_config: dict[str, str | None] | None,
) -> tuple[str | None, str, str, str]:
    if provider_config is None:
        return openai_api_key(), openai_api_url(), openai_api_model(), "custom-openai"
    return (
        provider_config.get("api_key") or openai_api_key(),
        provider_config.get("api_url") or openai_api_url(),
        provider_config.get("model") or openai_api_model(),
        provider_config.get("provider_id") or "custom-openai",
    )


def _anthropic_connection(
    provider_config: dict[str, str | None] | None,
) -> tuple[str | None, str, str, str]:
    if provider_config is None:
        return anthropic_api_key(), anthropic_api_url(), anthropic_api_model(), "custom-anthropic"
    return (
        provider_config.get("api_key") or anthropic_api_key(),
        provider_config.get("api_url") or anthropic_api_url(),
        provider_config.get("model") or anthropic_api_model(),
        provider_config.get("provider_id") or "custom-anthropic",
    )


def _raise_missing_provider() -> None:
    raise ProviderInvocationError(
        "provider_not_configured",
        "未配置可用的模型服务，无法完成该工作流步骤。",
        retryable=False,
    )


def _invoke_openai_compatible(
    *,
    system_prompt: str,
    user_prompt: str,
    provider_config: dict[str, str | None] | None,
    max_output_tokens: int,
    temperature: float,
    reasoning_effort: str | None,
) -> StructuredModelResult:
    api_key, raw_url, model, provider_id = _openai_connection(provider_config)
    if not api_key:
        _raise_missing_provider()
    try:
        request = resolve_provider_chat_request("openai", provider_id, raw_url, api_key)
    except ProviderProfileError as exc:
        raise ProviderInvocationError(
            "provider_request_invalid",
            "Provider endpoint configuration is invalid.",
            retryable=False,
        ) from exc
    payload: dict[str, object] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_output_tokens,
    }
    if reasoning_effort in _OPENAI_REASONING_EFFORT and _supports_reasoning_effort(request.url, model):
        payload["reasoning_effort"] = _OPENAI_REASONING_EFFORT[reasoning_effort]
    try:
        response = httpx.post(
            request.url,
            headers=request.headers,
            json=payload,
            timeout=90.0,
        )
    except httpx.TimeoutException as exc:
        raise ProviderInvocationError(
            "provider_timeout",
            "模型服务请求超时，正在按策略重试。",
            retryable=True,
        ) from exc
    except httpx.RequestError as exc:
        raise ProviderInvocationError(
            "provider_unavailable",
            "模型服务暂时不可用，正在按策略重试。",
            retryable=True,
        ) from exc
    if response.status_code >= 400:
        raise provider_error_for_status(response.status_code)
    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ProviderInvocationError(
            "provider_response_invalid",
            "模型服务返回了无法解析的结果，正在按策略重试。",
            retryable=True,
        ) from exc
    if not isinstance(content, str) or not content.strip():
        raise ProviderInvocationError(
            "provider_response_invalid",
            "模型服务未返回可用结果，正在按策略重试。",
            retryable=True,
        )
    return StructuredModelResult(
        content=content,
        model_used=model,
        provider_type="openai",
        usage=normalize_openai_usage(data),
    )


def _invoke_anthropic(
    *,
    system_prompt: str,
    user_prompt: str,
    provider_config: dict[str, str | None] | None,
    max_output_tokens: int,
    temperature: float,
    reasoning_effort: str | None,
) -> StructuredModelResult:
    api_key, raw_url, model, provider_id = _anthropic_connection(provider_config)
    if not api_key:
        _raise_missing_provider()
    try:
        request = resolve_provider_chat_request("anthropic", provider_id, raw_url, api_key)
    except ProviderProfileError as exc:
        raise ProviderInvocationError(
            "provider_request_invalid",
            "Provider endpoint configuration is invalid.",
            retryable=False,
        ) from exc
    payload: dict[str, object] = {
        "model": model,
        "max_tokens": max_output_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    if reasoning_effort in _ADAPTIVE_THINKING_EFFORT and _supports_adaptive_thinking(request.url, model):
        payload["thinking"] = {"type": "adaptive"}
        payload["output_config"] = {"effort": _ADAPTIVE_THINKING_EFFORT[reasoning_effort]}
    else:
        payload["temperature"] = temperature
    if (
        reasoning_effort in _THINKING_BUDGETS
        and _supports_thinking(request.url, model)
        and not _supports_adaptive_thinking(request.url, model)
    ):
        payload["thinking"] = {
            "type": "enabled",
            "budget_tokens": _THINKING_BUDGETS[reasoning_effort],
        }
    try:
        response = httpx.post(
            request.url,
            headers=request.headers,
            json=payload,
            timeout=120.0,
        )
    except httpx.TimeoutException as exc:
        raise ProviderInvocationError(
            "provider_timeout",
            "模型服务请求超时，正在按策略重试。",
            retryable=True,
        ) from exc
    except httpx.RequestError as exc:
        raise ProviderInvocationError(
            "provider_unavailable",
            "模型服务暂时不可用，正在按策略重试。",
            retryable=True,
        ) from exc
    if response.status_code >= 400:
        raise provider_error_for_status(response.status_code)
    try:
        data = response.json()
        blocks = data.get("content", [])
        content = "".join(
            block["text"]
            for block in blocks
            if isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ProviderInvocationError(
            "provider_response_invalid",
            "模型服务返回了无法解析的结果，正在按策略重试。",
            retryable=True,
        ) from exc
    if not content.strip():
        raise ProviderInvocationError(
            "provider_response_invalid",
            "模型服务未返回可用结果，正在按策略重试。",
            retryable=True,
        )
    returned_model = data.get("model") if isinstance(data.get("model"), str) else model
    return StructuredModelResult(
        content=content,
        model_used=returned_model,
        provider_type="anthropic",
        usage=normalize_anthropic_usage(data),
    )


def invoke_structured_text(
    *,
    system_prompt: str,
    user_prompt: str,
    provider_config: dict[str, str | None] | None,
    provider_type: str,
    max_output_tokens: int,
    temperature: float,
    reasoning_effort: str | None = None,
) -> StructuredModelResult:
    """Invoke one bounded model request for a structured workflow task."""
    bounded_system = with_untrusted_context_guard(
        system_prompt,
        max_characters=_MAX_SYSTEM_PROMPT_CHARACTERS,
    )
    bounded_user = user_prompt[:_MAX_USER_PROMPT_CHARACTERS]
    bounded_output = _bounded_output_tokens(max_output_tokens)
    if provider_type == "anthropic":
        return _invoke_anthropic(
            system_prompt=bounded_system,
            user_prompt=bounded_user,
            provider_config=provider_config,
            max_output_tokens=bounded_output,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
        )
    return _invoke_openai_compatible(
        system_prompt=bounded_system,
        user_prompt=bounded_user,
        provider_config=provider_config,
        max_output_tokens=bounded_output,
        temperature=temperature,
        reasoning_effort=reasoning_effort,
    )
