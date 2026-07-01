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

from app.providers.endpoints import normalize_provider_base_url

ReasoningEffort = Literal["low", "medium", "high", "ultra", "max"]

_OPENAI_REASONING_EFFORT: dict[str, str] = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "ultra": "high",
    "max": "high",
}

_ANTHROPIC_REASONING_EFFORT: dict[str, str] = {
    "low": "low",
    "medium": "medium",
    "high": "high",
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


def get_agent_llm(
    provider_type: str = "openai",
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
        return _make(provider_type, api_key, base_url, model, reasoning_effort=reasoning_effort)

    # 2. Dedicated assistant LLM config
    asst_key = os.getenv("DOCPILOT_ASSISTANT_API_KEY")
    if asst_key:
        return _make(
            os.getenv("DOCPILOT_ASSISTANT_PROTOCOL", "openai"),
            asst_key,
            os.getenv("DOCPILOT_ASSISTANT_BASE_URL", "https://api.deepseek.com/v1"),
            os.getenv("DOCPILOT_ASSISTANT_MODEL", "deepseek-chat"),
            reasoning_effort=reasoning_effort,
        )

    # 3. DeepSeek env vars
    ds_key = os.getenv("DEEPSEEK_API_KEY")
    if ds_key:
        return _make(
            "openai",
            ds_key,
            os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
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
            reasoning_effort=reasoning_effort,
        )

    # No key configured — will fail at call time
    return _make(
        "openai",
        "sk-placeholder",
        "https://api.deepseek.com/v1",
        "deepseek-chat",
        reasoning_effort=reasoning_effort,
    )


def _make(
    provider_type: str,
    api_key: str,
    base_url: str | None,
    model: str,
    reasoning_effort: ReasoningEffort | None = None,
) -> BaseChatModel:
    normalized_base_url = normalize_provider_base_url(provider_type, base_url)
    if provider_type == "anthropic":
        kwargs: dict[str, object] = {}
        if reasoning_effort and _supports_anthropic_effort(normalized_base_url, model):
            kwargs["effort"] = _ANTHROPIC_REASONING_EFFORT[reasoning_effort]
        return ChatAnthropic(
            api_key=api_key,
            base_url=normalized_base_url,
            model_name=model,
            streaming=True,
            temperature=0.7,
            **kwargs,
        )

    kwargs: dict[str, object] = {}
    if reasoning_effort and _supports_openai_reasoning(normalized_base_url, model):
        kwargs["reasoning_effort"] = _OPENAI_REASONING_EFFORT[reasoning_effort]
    return ChatOpenAI(
        api_key=api_key,
        base_url=normalized_base_url,
        model=model,
        streaming=True,
        temperature=0.7,
        **kwargs,
    )
