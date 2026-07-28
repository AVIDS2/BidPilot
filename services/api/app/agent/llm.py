"""LLM factory for the assistant agent.

Three-layer independent LLM configuration:
1. Embedding API    — DOCPILOT_EMBEDDING_* (for vector search)
2. Workflow Agent   — DOCPILOT_PROVIDER_DOMESTIC_* (for drafting workflow)
3. Assistant Agent  — DOCPILOT_ASSISTANT_* (for conversational assistant)

Each layer has its own API key, base URL, and model.
Currently layers 2 and 3 may happen to point to the same provider,
but they are configured independently.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import os
from typing import Any, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.providers.endpoints import normalize_provider_base_url, profile_client_headers
from app.runtime.model_limits import OPERATOR_PLANNER_MAX_OUTPUT_TOKENS

ReasoningEffort = Literal["low", "medium", "high", "extra", "max"]

_OPENAI_REASONING_EFFORT: dict[str, str] = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "extra": "high",
    "max": "high",
}

_ANTHROPIC_REASONING_EFFORT: dict[str, str] = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "extra": "xhigh",
    "max": "max",
}


class AgentModelConfigurationError(ValueError):
    """Raised before a run starts when no safe model configuration exists."""


@dataclass(frozen=True)
class ResolvedAgentModel:
    """The complete server-side model selection for one assistant run.

    ``api_key`` deliberately stays out of repr/log output. A caller must either
    provide a complete BYOK configuration or select one complete platform
    configuration from the environment; mixing those sources is not allowed.
    """

    provider_type: str
    provider_id: str | None
    api_key: str = field(repr=False)
    base_url: str | None
    model: str


def resolve_agent_model(
    *,
    provider_type: str = "openai",
    provider_id: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    environment: Mapping[str, str] | None = None,
) -> ResolvedAgentModel:
    """Resolve one explicit assistant model without placeholder credentials.

    The old factory silently created a DeepSeek client with a fake key and a
    guessed model when configuration was incomplete. That made a deployment
    failure look like an Agent reasoning failure. This resolver keeps the
    provider/model choice deterministic and fails before a RuntimeRun is made.
    """

    if api_key is not None or model is not None:
        if not api_key or not api_key.strip():
            raise AgentModelConfigurationError("所选模型提供商缺少 API 密钥。")
        if not model or not model.strip():
            raise AgentModelConfigurationError("所选模型提供商缺少模型名称。")
        return ResolvedAgentModel(
            provider_type=provider_type or "openai",
            provider_id=provider_id,
            api_key=api_key.strip(),
            base_url=base_url.strip() if base_url and base_url.strip() else None,
            model=model.strip(),
        )

    env = environment if environment is not None else os.environ

    assistant_key = _env_value(env, "DOCPILOT_ASSISTANT_API_KEY")
    if assistant_key:
        return _platform_model(
            api_key=assistant_key,
            provider_type=_env_value(env, "DOCPILOT_ASSISTANT_PROTOCOL") or "openai",
            provider_id=_env_value(env, "DOCPILOT_ASSISTANT_PROVIDER_ID") or "deepseek",
            base_url=(
                _env_value(env, "DOCPILOT_ASSISTANT_BASE_URL")
                or _env_value(env, "DEEPSEEK_BASE_URL")
                or "https://api.deepseek.com/v1"
            ),
            model=(
                _env_value(env, "DOCPILOT_ASSISTANT_MODEL")
                or _env_value(env, "DEEPSEEK_MODEL")
            ),
            source_name="DOCPILOT_ASSISTANT_*",
        )

    deepseek_key = _env_value(env, "DEEPSEEK_API_KEY")
    if deepseek_key:
        return _platform_model(
            api_key=deepseek_key,
            provider_type="openai",
            provider_id="deepseek",
            base_url=_env_value(env, "DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1",
            model=_env_value(env, "DEEPSEEK_MODEL"),
            source_name="DEEPSEEK_*",
        )

    domestic_key = (
        _env_value(env, "DOCPILOT_PROVIDER_DOMESTIC_API_KEY")
        or _env_value(env, "ALIYUN_API_KEY")
        or _env_value(env, "DASHSCOPE_API_KEY")
    )
    if domestic_key:
        return _platform_model(
            api_key=domestic_key,
            provider_type="openai",
            provider_id="dashscope",
            base_url=(
                _env_value(env, "DOCPILOT_PROVIDER_DOMESTIC_BASE_URL")
                or "https://dashscope.aliyuncs.com/compatible-mode/v1"
            ),
            model=(
                _env_value(env, "DOCPILOT_PROVIDER_DOMESTIC_MODEL")
                or _env_value(env, "DOCPILOT_LLM_MODEL_PRIMARY")
            ),
            source_name="DOCPILOT_PROVIDER_DOMESTIC_*",
        )

    raise AgentModelConfigurationError(
        "平台对话模型尚未配置。请由管理员配置服务器端模型环境变量，或在设置中选择自己的提供商。"
    )


def _env_value(environment: Mapping[str, str], name: str) -> str | None:
    value = environment.get(name)
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _platform_model(
    *,
    api_key: str,
    provider_type: str,
    provider_id: str,
    base_url: str,
    model: str | None,
    source_name: str,
) -> ResolvedAgentModel:
    if not model:
        raise AgentModelConfigurationError(f"{source_name} 已提供密钥，但缺少对应的模型名称。")
    return ResolvedAgentModel(
        provider_type=provider_type,
        provider_id=provider_id,
        api_key=api_key,
        base_url=base_url,
        model=model,
    )


def _supports_openai_reasoning(base_url: str, model: str) -> bool:
    """Only send native reasoning controls to the official OpenAI endpoint.

    Many providers advertise OpenAI compatibility but reject newer model-control
    fields. Non-official providers still receive reasoning guidance through the
    agent system prompt.
    """
    return "api.openai.com" in base_url.lower() and model.lower().startswith(("o1", "o3", "o4", "gpt-5"))


def _supports_anthropic_effort(base_url: str, model: str) -> bool:
    normalized = f"{base_url} {model}".lower()
    return "api.anthropic.com" in normalized and (
        "claude-3-7" in normalized or "claude-sonnet-4" in normalized or "claude-opus-4" in normalized
    )


def _supports_anthropic_adaptive_thinking(base_url: str, model: str) -> bool:
    normalized = f"{base_url} {model}".lower()
    return "api.anthropic.com" in normalized and any(
        marker in normalized
        for marker in ("claude-opus-4-7", "claude-opus-4-8")
    )


def get_agent_llm(
    provider_type: str = "openai",
    provider_id: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    reasoning_effort: ReasoningEffort | None = None,
) -> BaseChatModel:
    """Create a chat model instance for the assistant agent.

    Resolution priority:
    1. Explicit parameters (user BYOK from provider_config table)
    2. DOCPILOT_ASSISTANT_* env vars (dedicated assistant LLM)
    3. DEEPSEEK_* env vars (legacy platform config)
    4. DOCPILOT_PROVIDER_DOMESTIC_* env vars (shared platform provider)

    A missing configuration is an explicit server-side error. Never create a
    placeholder client which could fail later with a misleading model error.
    """
    resolved = resolve_agent_model(
        provider_type=provider_type,
        provider_id=provider_id,
        api_key=api_key,
        base_url=base_url,
        model=model,
    )
    return _make(
        resolved.provider_type,
        resolved.api_key,
        resolved.base_url,
        resolved.model,
        provider_id=resolved.provider_id,
        reasoning_effort=reasoning_effort,
    )


def _make(
    provider_type: str,
    api_key: str,
    base_url: str | None,
    model: str,
    provider_id: str | None = None,
    reasoning_effort: ReasoningEffort | None = None,
) -> BaseChatModel:
    normalized_base_url = normalize_provider_base_url(provider_type, base_url, provider_id)
    client_headers = profile_client_headers(provider_type, provider_id, api_key)
    secret_api_key = SecretStr(api_key)
    if provider_type == "anthropic":
        anthropic_kwargs: dict[str, Any] = {}
        uses_adaptive_thinking = _supports_anthropic_adaptive_thinking(normalized_base_url, model)
        if reasoning_effort and _supports_anthropic_effort(normalized_base_url, model):
            anthropic_kwargs["effort"] = _ANTHROPIC_REASONING_EFFORT[reasoning_effort]
        if reasoning_effort and uses_adaptive_thinking:
            anthropic_kwargs["thinking"] = {"type": "adaptive"}
        return ChatAnthropic(
            api_key=secret_api_key,
            base_url=normalized_base_url,
            model_name=model,
            max_tokens_to_sample=OPERATOR_PLANNER_MAX_OUTPUT_TOKENS,
            streaming=True,
            temperature=None if uses_adaptive_thinking else 0.7,
            default_headers=client_headers or None,
            **anthropic_kwargs,
        )

    openai_kwargs: dict[str, Any] = {}
    if reasoning_effort and _supports_openai_reasoning(normalized_base_url, model):
        openai_kwargs["reasoning_effort"] = _OPENAI_REASONING_EFFORT[reasoning_effort]
    # langchain-openai normalizes its legacy `max_tokens` argument to this
    # current Chat Completions field even for custom base URLs. Pass it
    # explicitly so the planner boundary is visible and warning-free.
    openai_kwargs["max_completion_tokens"] = OPERATOR_PLANNER_MAX_OUTPUT_TOKENS
    return ChatOpenAI(
        api_key=secret_api_key,
        base_url=normalized_base_url,
        model=model,
        streaming=True,
        temperature=0.7,
        default_headers=client_headers or None,
        **openai_kwargs,
    )
