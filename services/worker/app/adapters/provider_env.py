"""Environment-based provider configuration for worker adapters.

This module centralizes official platform provider env handling. User-supplied
BYOK credentials still flow through ``provider_config`` and never through here.
"""

from __future__ import annotations

import os

DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_CHAT_MODEL = "qwen3.5-flash"
DASHSCOPE_EMBEDDING_MODEL = "text-embedding-v4"


def _first_present(names: list[tuple[str, str]]) -> tuple[str | None, str | None]:
    for name, family in names:
        value = os.environ.get(name)
        if value:
            return value, family
    return None, None


def _endpoint(base_url: str, suffix: str) -> str:
    return f"{base_url.rstrip('/')}/{suffix.lstrip('/')}"


def chat_api_key() -> str | None:
    key, _family = _first_present(
        [
            ("LLM_API_KEY", "legacy"),
            ("DOCPILOT_PROVIDER_DOMESTIC_API_KEY", "domestic"),
            ("ALIYUN_API_KEY", "domestic"),
            ("DASHSCOPE_API_KEY", "domestic"),
            ("DOCPILOT_PROVIDER_OPENAI_API_KEY", "openai"),
            ("OPENAI_API_KEY", "openai"),
        ]
    )
    return key


def chat_api_url(default_url: str) -> str:
    explicit_url = os.environ.get("LLM_API_URL")
    if explicit_url:
        return explicit_url

    _key, family = _first_present(
        [
            ("LLM_API_KEY", "legacy"),
            ("DOCPILOT_PROVIDER_DOMESTIC_API_KEY", "domestic"),
            ("ALIYUN_API_KEY", "domestic"),
            ("DASHSCOPE_API_KEY", "domestic"),
            ("DOCPILOT_PROVIDER_OPENAI_API_KEY", "openai"),
            ("OPENAI_API_KEY", "openai"),
        ]
    )

    if family == "domestic":
        base_url = os.environ.get("DOCPILOT_PROVIDER_DOMESTIC_BASE_URL", DASHSCOPE_BASE_URL)
        return _endpoint(base_url, "chat/completions")

    if family == "openai":
        base_url = os.environ.get("DOCPILOT_PROVIDER_OPENAI_BASE_URL")
        if base_url:
            return _endpoint(base_url, "chat/completions")

    return default_url


def chat_model(default_model: str) -> str:
    explicit_model = os.environ.get("LLM_MODEL")
    if explicit_model:
        return explicit_model

    _key, family = _first_present(
        [
            ("LLM_API_KEY", "legacy"),
            ("DOCPILOT_PROVIDER_DOMESTIC_API_KEY", "domestic"),
            ("ALIYUN_API_KEY", "domestic"),
            ("DASHSCOPE_API_KEY", "domestic"),
            ("DOCPILOT_PROVIDER_OPENAI_API_KEY", "openai"),
            ("OPENAI_API_KEY", "openai"),
        ]
    )
    if family == "domestic":
        return os.environ.get("DOCPILOT_LLM_MODEL_PRIMARY", DASHSCOPE_CHAT_MODEL)
    return default_model


def embedding_api_key() -> str | None:
    key, _family = _first_present(
        [
            ("EMBEDDING_API_KEY", "legacy"),
            ("DOCPILOT_PROVIDER_DOMESTIC_API_KEY", "domestic"),
            ("ALIYUN_API_KEY", "domestic"),
            ("DASHSCOPE_API_KEY", "domestic"),
            ("DOCPILOT_PROVIDER_OPENAI_API_KEY", "openai"),
            ("OPENAI_API_KEY", "openai"),
        ]
    )
    return key


def embedding_api_url(default_url: str) -> str:
    explicit_url = os.environ.get("EMBEDDING_API_URL")
    if explicit_url:
        return explicit_url

    _key, family = _first_present(
        [
            ("EMBEDDING_API_KEY", "legacy"),
            ("DOCPILOT_PROVIDER_DOMESTIC_API_KEY", "domestic"),
            ("ALIYUN_API_KEY", "domestic"),
            ("DASHSCOPE_API_KEY", "domestic"),
            ("DOCPILOT_PROVIDER_OPENAI_API_KEY", "openai"),
            ("OPENAI_API_KEY", "openai"),
        ]
    )

    if family == "domestic":
        base_url = os.environ.get("DOCPILOT_PROVIDER_DOMESTIC_BASE_URL", DASHSCOPE_BASE_URL)
        return _endpoint(base_url, "embeddings")

    if family == "openai":
        base_url = os.environ.get("DOCPILOT_PROVIDER_OPENAI_BASE_URL")
        if base_url:
            return _endpoint(base_url, "embeddings")

    return default_url


def embedding_model(default_model: str) -> str:
    explicit_model = os.environ.get("EMBEDDING_MODEL")
    if explicit_model:
        return explicit_model

    _key, family = _first_present(
        [
            ("EMBEDDING_API_KEY", "legacy"),
            ("DOCPILOT_PROVIDER_DOMESTIC_API_KEY", "domestic"),
            ("ALIYUN_API_KEY", "domestic"),
            ("DASHSCOPE_API_KEY", "domestic"),
            ("DOCPILOT_PROVIDER_OPENAI_API_KEY", "openai"),
            ("OPENAI_API_KEY", "openai"),
        ]
    )
    if family == "domestic":
        return os.environ.get("DOCPILOT_EMBEDDING_MODEL_TEXT", DASHSCOPE_EMBEDDING_MODEL)
    return default_model
