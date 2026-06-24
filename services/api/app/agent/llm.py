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

from langchain_openai import ChatOpenAI


def get_agent_llm(
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> ChatOpenAI:
    """Create a ChatOpenAI instance for the assistant agent.

    Resolution priority:
    1. Explicit parameters (user BYOK from provider_config table)
    2. DOCPILOT_ASSISTANT_* env vars (dedicated assistant LLM)
    3. DEEPSEEK_* env vars (legacy fallback)
    4. DOCPILOT_PROVIDER_DOMESTIC_* env vars (shared platform provider)
    """
    # 1. User BYOK — highest priority
    if api_key and base_url and model:
        return _make(api_key, base_url, model)

    # 2. Dedicated assistant LLM config
    asst_key = os.getenv("DOCPILOT_ASSISTANT_API_KEY")
    if asst_key:
        return _make(
            asst_key,
            os.getenv("DOCPILOT_ASSISTANT_BASE_URL", "https://api.deepseek.com/v1"),
            os.getenv("DOCPILOT_ASSISTANT_MODEL", "deepseek-chat"),
        )

    # 3. DeepSeek env vars
    ds_key = os.getenv("DEEPSEEK_API_KEY")
    if ds_key:
        return _make(
            ds_key,
            os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        )

    # 4. Shared platform provider (DashScope/Qwen) — last resort
    domestic_key = (
        os.getenv("DOCPILOT_PROVIDER_DOMESTIC_API_KEY")
        or os.getenv("ALIYUN_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
    )
    if domestic_key:
        return _make(
            domestic_key,
            os.getenv("DOCPILOT_PROVIDER_DOMESTIC_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            os.getenv("DOCPILOT_LLM_MODEL_PRIMARY", "qwen3.5-flash"),
        )

    # No key configured — will fail at call time
    return _make("sk-placeholder", "https://api.deepseek.com/v1", "deepseek-chat")


def _make(api_key: str, base_url: str, model: str) -> ChatOpenAI:
    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model,
        streaming=True,
        temperature=0.7,
    )
