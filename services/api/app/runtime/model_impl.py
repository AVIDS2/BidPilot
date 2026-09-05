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
from contracts.chat_config import (
    DEEPSEEK_CHAT_COMPLETIONS_BASE_URL,
    DEEPSEEK_V4_FLASH_MODEL,
    MIMO_CHAT_COMPLETIONS_BASE_URL,
    MIMO_V2_5_PRO_MODEL,
    OPENCODE_GO_CHAT_COMPLETIONS_BASE_URL,
    OPENCODE_GO_DEEPSEEK_V4_FLASH_MODEL,
)

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

_DEEPSEEK_REASONING_EFFORT: dict[str, str] = {
    "low": "low",
    "medium": "high",
    "high": "high",
    "extra": "high",
    "max": "max",
}


class DeepSeekChatOpenAI(ChatOpenAI):
    """Keep DeepSeek V4's public reasoning stream on LangChain chunks.

    DeepSeek emits ``delta.reasoning_content`` in its OpenAI-compatible
    Chat Completions stream.  The installed langchain-openai converter keeps
    tool chunks and ordinary content but drops that provider field.  Preserve
    it in ``additional_kwargs`` so the governed runtime can persist and replay
    exactly what the provider returned, without synthesizing a thought trace.
    """

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict[str, Any],
        default_chunk_class: type,
        base_generation_info: dict[str, Any] | None,
    ) -> Any:
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk,
            default_chunk_class,
            base_generation_info,
        )
        if generation_chunk is None:
            return None
        choices = chunk.get("choices", []) or chunk.get("chunk", {}).get("choices", [])
        if not choices or not isinstance(choices[0], dict):
            return generation_chunk
        delta = choices[0].get("delta")
        reasoning = delta.get("reasoning_content") if isinstance(delta, dict) else None
        if isinstance(reasoning, str) and reasoning:
            generation_chunk.message.additional_kwargs["reasoning_content"] = reasoning
        return generation_chunk


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
    assistant_provider_id = _env_value(env, "DOCPILOT_ASSISTANT_PROVIDER_ID")
    mimo_key = _env_value(env, "MIMO_API_KEY") or _env_value(env, "XIAOMI_API_KEY")
    uses_mimo_profile = (assistant_provider_id or "").casefold() in {
        "mimo",
        "xiaomi",
        "xiaomi-token-plan-cn",
        "xiaomi-token-plan-ams",
        "xiaomi-token-plan-sgp",
    }

    # A dedicated MiMo credential wins over a stale generic assistant key when
    # the configured profile is MiMo. This keeps provider, endpoint and model
    # from silently drifting apart during local or production restarts.
    if mimo_key and (not assistant_key or uses_mimo_profile):
        return _platform_model(
            api_key=mimo_key,
            provider_type="openai",
            provider_id="mimo",
            base_url=_env_value(env, "MIMO_BASE_URL") or MIMO_CHAT_COMPLETIONS_BASE_URL,
            model=_env_value(env, "MIMO_MODEL") or MIMO_V2_5_PRO_MODEL,
            source_name="MIMO_API_KEY",
        )

    if assistant_key:
        assistant_provider_id = assistant_provider_id or "deepseek"
        uses_opencode_go = assistant_provider_id.casefold() == "opencode-go"
        uses_mimo = assistant_provider_id.casefold() in {
            "mimo",
            "xiaomi",
            "xiaomi-token-plan-cn",
            "xiaomi-token-plan-ams",
            "xiaomi-token-plan-sgp",
        }
        return _platform_model(
            api_key=assistant_key,
            provider_type=_env_value(env, "DOCPILOT_ASSISTANT_PROTOCOL") or "openai",
            provider_id=assistant_provider_id,
            base_url=(
                _env_value(env, "DOCPILOT_ASSISTANT_BASE_URL")
                or (
                    _env_value(env, "OPENCODE_BASE_URL") or OPENCODE_GO_CHAT_COMPLETIONS_BASE_URL
                    if uses_opencode_go
                    else _env_value(env, "MIMO_BASE_URL") or MIMO_CHAT_COMPLETIONS_BASE_URL
                    if uses_mimo
                    else _env_value(env, "DEEPSEEK_BASE_URL") or DEEPSEEK_CHAT_COMPLETIONS_BASE_URL
                )
            ),
            model=(
                _env_value(env, "DOCPILOT_ASSISTANT_MODEL")
                or (
                    _env_value(env, "OPENCODE_MODEL") or OPENCODE_GO_DEEPSEEK_V4_FLASH_MODEL
                    if uses_opencode_go
                    else _env_value(env, "MIMO_MODEL") or MIMO_V2_5_PRO_MODEL
                    if uses_mimo
                    else _env_value(env, "DEEPSEEK_MODEL")
                    or (DEEPSEEK_V4_FLASH_MODEL if assistant_provider_id == "deepseek" else None)
                )
            ),
            source_name="DOCPILOT_ASSISTANT_*",
        )

    opencode_key = _env_value(env, "OPENCODE_API_KEY")
    if opencode_key:
        return _platform_model(
            api_key=opencode_key,
            provider_type="openai",
            provider_id="opencode-go",
            base_url=_env_value(env, "OPENCODE_BASE_URL") or OPENCODE_GO_CHAT_COMPLETIONS_BASE_URL,
            model=_env_value(env, "OPENCODE_MODEL") or OPENCODE_GO_DEEPSEEK_V4_FLASH_MODEL,
            source_name="OPENCODE_*",
        )

    deepseek_key = _env_value(env, "DEEPSEEK_API_KEY")
    if deepseek_key:
        return _platform_model(
            api_key=deepseek_key,
            provider_type="openai",
            provider_id="deepseek",
            base_url=_env_value(env, "DEEPSEEK_BASE_URL") or DEEPSEEK_CHAT_COMPLETIONS_BASE_URL,
            model=_env_value(env, "DEEPSEEK_MODEL") or DEEPSEEK_V4_FLASH_MODEL,
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


def _supports_deepseek_v4_thinking(
    provider_id: str | None,
    base_url: str,
    model: str,
) -> bool:
    """Return whether this is the official DeepSeek V4 thinking surface."""
    is_deepseek = (provider_id or "").lower() == "deepseek" or "api.deepseek.com" in base_url.lower()
    return is_deepseek and model.lower().startswith("deepseek-v4-")


def _uses_opencode_go_deepseek_v4(
    provider_id: str | None,
    base_url: str,
    model: str,
) -> bool:
    return (
        (provider_id or "").lower() == "opencode-go"
        or "opencode.ai/zen/go" in base_url.lower()
    ) and model.lower().startswith("deepseek-v4-")


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
    3. OPENCODE_* env vars (OpenCode Go platform profile)
    4. DEEPSEEK_* env vars (legacy platform config)
    5. DOCPILOT_PROVIDER_DOMESTIC_* env vars (shared platform provider)

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


def get_required_tool_choice_llm(llm: BaseChatModel) -> BaseChatModel:
    """Return a compatible model for a server-enforced tool-call retry.

    DeepSeek V4 accepts normal tool calls while thinking is enabled, but rejects
    the OpenAI-compatible ``tool_choice`` control in that mode.  A harness must
    occasionally require one tool call after the model has already promised a
    business action in prose.  Reusing the thinking client would turn that
    correction into a provider 400 instead of a governed approval/action.

    Only that narrowly-scoped retry uses a fresh non-thinking client.  The
    normal reasoning turn keeps its configured thinking mode and provider
    settings.  Other providers retain their existing client because their
    tool-choice semantics are provider-specific.
    """
    model_name = str(getattr(llm, "model_name", ""))
    base_url = str(getattr(llm, "openai_api_base", ""))
    is_official_deepseek = isinstance(llm, DeepSeekChatOpenAI) and _supports_deepseek_v4_thinking(
        "deepseek", base_url, model_name
    )
    is_opencode_go = _uses_opencode_go_deepseek_v4(None, base_url, model_name)
    if not (is_official_deepseek or is_opencode_go):
        return llm

    client_class = DeepSeekChatOpenAI if is_official_deepseek else ChatOpenAI
    source_api_key: SecretStr | None = getattr(llm, "openai_api_key", None)
    if isinstance(source_api_key, str):
        source_api_key = SecretStr(source_api_key)
    elif source_api_key is not None and not isinstance(source_api_key, SecretStr):
        source_api_key = SecretStr(str(source_api_key))
    source_base_url = str(getattr(llm, "openai_api_base", "") or "")
    return client_class(
        api_key=source_api_key,
        base_url=source_base_url,
        model=model_name,
        streaming=True,
        temperature=0.1 if is_official_deepseek else 0.7,
        max_completion_tokens=getattr(llm, "max_tokens", None) or OPERATOR_PLANNER_MAX_OUTPUT_TOKENS,
        max_retries=getattr(llm, "max_retries", None),
        default_headers=getattr(llm, "default_headers", None),
        extra_body={"thinking": {"type": "disabled"}},
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
    uses_deepseek_v4_thinking = _supports_deepseek_v4_thinking(provider_id, normalized_base_url, model)
    uses_opencode_go_deepseek_v4 = _uses_opencode_go_deepseek_v4(provider_id, normalized_base_url, model)
    if reasoning_effort and uses_deepseek_v4_thinking:
        # DeepSeek V4 requires both the effort selector and an explicit
        # thinking opt-in.  ``extra`` is a product-level setting; Flash maps
        # it to the closest documented provider level, ``high``.
        openai_kwargs["reasoning_effort"] = _DEEPSEEK_REASONING_EFFORT[reasoning_effort]
        openai_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
    elif reasoning_effort and uses_opencode_go_deepseek_v4:
        # Pi's OpenCode Go adapter records that this route rejects a combined
        # ``thinking`` and ``reasoning_effort`` request for DeepSeek V4. The
        # product-level effort still shapes the server prompt; the gateway gets
        # only its stable native thinking switch.
        openai_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
    elif reasoning_effort and _supports_openai_reasoning(normalized_base_url, model):
        openai_kwargs["reasoning_effort"] = _OPENAI_REASONING_EFFORT[reasoning_effort]
    # langchain-openai normalizes its legacy `max_tokens` argument to this
    # current Chat Completions field even for custom base URLs. Pass it
    # explicitly so the planner boundary is visible and warning-free.
    openai_kwargs["max_completion_tokens"] = OPERATOR_PLANNER_MAX_OUTPUT_TOKENS
    chat_model_class = DeepSeekChatOpenAI if uses_deepseek_v4_thinking else ChatOpenAI
    return chat_model_class(
        api_key=secret_api_key,
        base_url=normalized_base_url,
        model=model,
        streaming=True,
        temperature=None if uses_deepseek_v4_thinking else 0.7,
        default_headers=client_headers or None,
        **openai_kwargs,
    )
