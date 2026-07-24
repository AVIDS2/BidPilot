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

import os
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.providers.endpoints import normalize_provider_base_url, profile_client_headers
from app.runtime.model_limits import OPERATOR_PLANNER_MAX_OUTPUT_TOKENS

ReasoningEffort = Literal["low", "medium", "high", "extra", "max", "ultra"]

_OPENAI_REASONING_EFFORT: dict[str, str] = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "extra": "high",
    "ultra": "high",
    "max": "high",
}

_ANTHROPIC_REASONING_EFFORT: dict[str, str] = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "extra": "xhigh",
    "ultra": "xhigh",
    "max": "max",
}


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
    3. DEEPSEEK_* env vars (legacy fallback)
    4. DOCPILOT_PROVIDER_DOMESTIC_* env vars (shared platform provider)
    """
    # 1. User BYOK — highest priority
    if api_key and model:
        return _make(
            provider_type,
            api_key,
            base_url,
            model,
            provider_id=provider_id,
            reasoning_effort=reasoning_effort,
        )

    # 2. Dedicated assistant LLM config
    asst_key = os.getenv("DOCPILOT_ASSISTANT_API_KEY")
    if asst_key:
        return _make(
            os.getenv("DOCPILOT_ASSISTANT_PROTOCOL", "openai"),
            asst_key,
            os.getenv("DOCPILOT_ASSISTANT_BASE_URL", "https://api.deepseek.com/v1"),
            os.getenv("DOCPILOT_ASSISTANT_MODEL", "deepseek-v4-flash"),
            provider_id=os.getenv("DOCPILOT_ASSISTANT_PROVIDER_ID", "deepseek"),
            reasoning_effort=reasoning_effort,
        )

    # 3. DeepSeek env vars
    ds_key = os.getenv("DEEPSEEK_API_KEY")
    if ds_key:
        return _make(
            "openai",
            ds_key,
            os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            provider_id="deepseek",
            reasoning_effort=reasoning_effort,
        )

    # 4. Shared platform provider (DashScope/Qwen) — last resort
    domestic_key = (
        os.getenv("DOCPILOT_PROVIDER_DOMESTIC_API_KEY")
        or os.getenv("ALIYUN_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
    )
    if domestic_key:
        return _make(
            "openai",
            domestic_key,
            os.getenv("DOCPILOT_PROVIDER_DOMESTIC_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            os.getenv("DOCPILOT_LLM_MODEL_PRIMARY", "qwen3.5-flash"),
            provider_id="dashscope",
            reasoning_effort=reasoning_effort,
        )

    # No key configured — will fail at call time
    return _make(
        "openai",
        "sk-placeholder",
        "https://api.deepseek.com/v1",
        "deepseek-v4-flash",
        provider_id="deepseek",
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
    if provider_type == "anthropic":
        kwargs: dict[str, object] = {}
        uses_adaptive_thinking = _supports_anthropic_adaptive_thinking(normalized_base_url, model)
        if reasoning_effort and _supports_anthropic_effort(normalized_base_url, model):
            kwargs["effort"] = _ANTHROPIC_REASONING_EFFORT[reasoning_effort]
        if reasoning_effort and uses_adaptive_thinking:
            kwargs["thinking"] = {"type": "adaptive"}
        return ChatAnthropic(
            api_key=api_key,
            base_url=normalized_base_url,
            model_name=model,
            max_tokens_to_sample=OPERATOR_PLANNER_MAX_OUTPUT_TOKENS,
            streaming=True,
            temperature=None if uses_adaptive_thinking else 0.7,
            default_headers=client_headers or None,
            **kwargs,
        )

    kwargs: dict[str, object] = {}
    if reasoning_effort and _supports_openai_reasoning(normalized_base_url, model):
        kwargs["reasoning_effort"] = _OPENAI_REASONING_EFFORT[reasoning_effort]
    # langchain-openai normalizes its legacy `max_tokens` argument to this
    # current Chat Completions field even for custom base URLs. Pass it
    # explicitly so the planner boundary is visible and warning-free.
    kwargs["max_completion_tokens"] = OPERATOR_PLANNER_MAX_OUTPUT_TOKENS
    return ChatOpenAI(
        api_key=api_key,
        base_url=normalized_base_url,
        model=model,
        streaming=True,
        temperature=0.7,
        default_headers=client_headers or None,
        **kwargs,
    )
