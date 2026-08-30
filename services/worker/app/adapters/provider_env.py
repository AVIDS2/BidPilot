"""Environment-based provider configuration for worker adapters.

This module centralizes official platform provider env handling. User-supplied
BYOK credentials still flow through ``provider_config`` and never through here.
"""

from __future__ import annotations

import os

from contracts.embedding_config import (
    DASHSCOPE_BASE_URL,
    embedding_api_key as embedding_api_key,
    embedding_api_url as embedding_api_url,
    embedding_dimensions as embedding_dimensions,
    embedding_model as embedding_model,
    embedding_provider_family as embedding_provider_family,
)
from contracts.chat_config import (
    DEEPSEEK_CHAT_COMPLETIONS_BASE_URL,
    DEEPSEEK_V4_FLASH_MODEL,
    MIMO_CHAT_COMPLETIONS_BASE_URL,
    MIMO_V2_5_PRO_MODEL,
    OPENCODE_GO_CHAT_COMPLETIONS_BASE_URL,
    OPENCODE_GO_DEEPSEEK_V4_FLASH_MODEL,
)

DASHSCOPE_CHAT_MODEL = "qwen3.5-flash"
_CHAT_KEY_SOURCES: list[tuple[str, str]] = [
    ("DOCPILOT_ASSISTANT_API_KEY", "assistant"),
    ("MIMO_API_KEY", "mimo"),
    ("XIAOMI_API_KEY", "mimo"),
    ("OPENCODE_API_KEY", "opencode-go"),
    # The platform gateway is the explicit production default. Keep legacy
    # variables as a fallback for existing self-hosted deployments only.
    ("LLM_API_KEY", "legacy"),
    ("DEEPSEEK_API_KEY", "deepseek"),
    ("DOCPILOT_PROVIDER_DOMESTIC_API_KEY", "domestic"),
    ("ALIYUN_API_KEY", "domestic"),
    ("DASHSCOPE_API_KEY", "domestic"),
    ("DOCPILOT_PROVIDER_OPENAI_API_KEY", "openai"),
    ("OPENAI_API_KEY", "openai"),
]

__all__ = [
    "chat_api_key",
    "chat_api_url",
    "chat_model",
    "embedding_api_key",
    "embedding_api_url",
    "embedding_dimensions",
    "embedding_model",
    "embedding_provider_family",
]


def _first_present(names: list[tuple[str, str]]) -> tuple[str | None, str | None]:
    for name, family in names:
        value = os.environ.get(name)
        if value:
            return value, family
    return None, None


def _endpoint(base_url: str, suffix: str) -> str:
    return f"{base_url.rstrip('/')}/{suffix.lstrip('/')}"


def chat_api_key() -> str | None:
    key, _family = _first_present(_CHAT_KEY_SOURCES)
    return key


def chat_api_url(default_url: str) -> str:
    _key, family = _first_present(_CHAT_KEY_SOURCES)

    # LLM_API_URL belongs to the legacy profile. It must not redirect an
    # explicitly configured platform gateway to an unrelated endpoint.
    if family == "legacy":
        explicit_url = os.environ.get("LLM_API_URL")
        if explicit_url:
            return explicit_url

    if family == "deepseek":
        base_url = os.environ.get("DEEPSEEK_BASE_URL") or DEEPSEEK_CHAT_COMPLETIONS_BASE_URL
        return _endpoint(base_url, "chat/completions")

    if family == "assistant":
        provider_id = (os.environ.get("DOCPILOT_ASSISTANT_PROVIDER_ID") or "").casefold()
        base_url = os.environ.get("DOCPILOT_ASSISTANT_BASE_URL")
        if not base_url:
            if provider_id in {"mimo", "xiaomi"}:
                base_url = os.environ.get("MIMO_BASE_URL") or MIMO_CHAT_COMPLETIONS_BASE_URL
            elif provider_id == "opencode-go":
                base_url = os.environ.get("OPENCODE_BASE_URL") or OPENCODE_GO_CHAT_COMPLETIONS_BASE_URL
            elif provider_id == "deepseek":
                base_url = os.environ.get("DEEPSEEK_BASE_URL") or DEEPSEEK_CHAT_COMPLETIONS_BASE_URL
        if base_url:
            return _endpoint(base_url, "chat/completions")
        return default_url

    if family == "opencode-go":
        base_url = os.environ.get("OPENCODE_BASE_URL") or OPENCODE_GO_CHAT_COMPLETIONS_BASE_URL
        return _endpoint(base_url, "chat/completions")

    if family == "domestic":
        base_url = os.environ.get("DOCPILOT_PROVIDER_DOMESTIC_BASE_URL") or DASHSCOPE_BASE_URL
        return _endpoint(base_url, "chat/completions")

    if family == "openai":
        base_url = os.environ.get("DOCPILOT_PROVIDER_OPENAI_BASE_URL")
        if base_url:
            return _endpoint(base_url, "chat/completions")

    return default_url


def chat_model(default_model: str) -> str:
    _key, family = _first_present(_CHAT_KEY_SOURCES)
    if family == "legacy":
        explicit_model = os.environ.get("LLM_MODEL")
        if explicit_model:
            return explicit_model
    if family == "deepseek":
        return os.environ.get("DEEPSEEK_MODEL") or DEEPSEEK_V4_FLASH_MODEL
    if family == "assistant":
        provider_id = (os.environ.get("DOCPILOT_ASSISTANT_PROVIDER_ID") or "").casefold()
        explicit_model = os.environ.get("DOCPILOT_ASSISTANT_MODEL")
        if explicit_model:
            return explicit_model
        if provider_id in {"mimo", "xiaomi"}:
            return os.environ.get("MIMO_MODEL") or MIMO_V2_5_PRO_MODEL
        if provider_id == "opencode-go":
            return os.environ.get("OPENCODE_MODEL") or OPENCODE_GO_DEEPSEEK_V4_FLASH_MODEL
        if provider_id == "deepseek":
            return os.environ.get("DEEPSEEK_MODEL") or DEEPSEEK_V4_FLASH_MODEL
        return default_model
    if family == "opencode-go":
        return os.environ.get("OPENCODE_MODEL") or OPENCODE_GO_DEEPSEEK_V4_FLASH_MODEL
    if family == "domestic":
        return (
            os.environ.get("DOCPILOT_PROVIDER_DOMESTIC_MODEL")
            or os.environ.get("DOCPILOT_LLM_MODEL_PRIMARY")
            or DASHSCOPE_CHAT_MODEL
        )
    return default_model


def chat_provider_id(default: str = "custom-openai") -> str:
    """Return the profile ID matching the selected environment provider."""
    _key, family = _first_present(_CHAT_KEY_SOURCES)
    if family == "assistant":
        return os.environ.get("DOCPILOT_ASSISTANT_PROVIDER_ID") or default
    if family == "mimo":
        return "mimo"
    if family == "opencode-go":
        return "opencode-go"
    if family == "deepseek":
        return "deepseek"
    if family == "domestic":
        base_url = os.environ.get("DOCPILOT_PROVIDER_DOMESTIC_BASE_URL") or ""
        return "mimo" if "xiaomimimo.com" in base_url.casefold() else "dashscope"
    if family == "openai":
        return "custom-openai"
    return default
