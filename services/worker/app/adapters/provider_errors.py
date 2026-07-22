"""Safe provider invocation errors shared by worker adapters."""

from __future__ import annotations

import os


class ProviderInvocationError(RuntimeError):
    """A classified provider failure that is safe to persist and render."""

    def __init__(self, error_code: str, public_message: str, *, retryable: bool) -> None:
        super().__init__(public_message)
        self.error_code = error_code
        self.public_message = public_message
        self.retryable = retryable


def allow_stub_llm() -> bool:
    """Allow deterministic drafting only outside production by default."""
    configured = os.environ.get("DOCPILOT_ALLOW_STUB_LLM")
    if configured is not None:
        return configured.strip().lower() in {"1", "true", "yes"}
    return os.environ.get("DOCPILOT_ENV", "local").lower() not in {"production", "staging"}


def provider_error_for_status(status_code: int) -> ProviderInvocationError:
    """Map an HTTP status to a stable, credential-safe provider error."""
    if status_code in {401, 403}:
        return ProviderInvocationError(
            "provider_auth_failed",
            "模型服务认证失败，请检查所选模型提供商的配置。",
            retryable=False,
        )
    if status_code == 404:
        return ProviderInvocationError(
            "provider_model_unavailable",
            "所选模型或服务端点不可用，请检查模型名称和服务商配置。",
            retryable=False,
        )
    if status_code in {400, 422}:
        return ProviderInvocationError(
            "provider_request_invalid",
            "模型服务拒绝了本次请求，请检查模型能力或配置。",
            retryable=False,
        )
    if status_code == 429:
        return ProviderInvocationError(
            "provider_rate_limited",
            "模型服务当前限流，正在按策略重试。",
            retryable=True,
        )
    if status_code in {408, 409} or status_code >= 500:
        return ProviderInvocationError(
            "provider_unavailable",
            "模型服务暂时不可用，正在按策略重试。",
            retryable=True,
        )
    return ProviderInvocationError(
        "provider_request_invalid",
        "模型服务未能处理本次请求。",
        retryable=False,
    )
