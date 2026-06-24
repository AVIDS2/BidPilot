"""LLM factory for the assistant agent."""

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
    1. Explicit parameters (user BYOK)
    2. Platform DeepSeek
    3. Platform DashScope/Qwen
    """
    if api_key and base_url and model:
        return ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            streaming=True,
            temperature=0.7,
        )

    # Platform DeepSeek
    ds_key = os.getenv("DEEPSEEK_API_KEY")
    if ds_key:
        return ChatOpenAI(
            api_key=ds_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            streaming=True,
            temperature=0.7,
        )

    # Platform DashScope / Qwen
    domestic_key = (
        os.getenv("DOCPILOT_PROVIDER_DOMESTIC_API_KEY")
        or os.getenv("ALIYUN_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
    )
    if domestic_key:
        return ChatOpenAI(
            api_key=domestic_key,
            base_url=os.getenv(
                "DOCPILOT_PROVIDER_DOMESTIC_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
            model=os.getenv("DOCPILOT_LLM_MODEL_PRIMARY", "qwen3.5-flash"),
            streaming=True,
            temperature=0.7,
        )

    # Fallback — should not happen in production
    return ChatOpenAI(
        api_key="sk-placeholder-not-real",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        streaming=True,
        temperature=0.7,
    )
