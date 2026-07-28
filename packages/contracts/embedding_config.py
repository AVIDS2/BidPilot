"""Shared environment resolution for platform-owned embedding providers.

The API and worker must derive the exact same embedding profile.  Provider
credentials remain process-local environment variables and never enter API
schemas, task payloads, logs, or database records.
"""

from __future__ import annotations

import os


DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_EMBEDDING_MODEL = "text-embedding-v4"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
OPENROUTER_EMBEDDING_DIMENSIONS = 1536

_EMBEDDING_KEY_SOURCES: tuple[tuple[str, str], ...] = (
    ("DOCPILOT_EMBEDDING_API_KEY", "platform"),
    ("EMBEDDING_API_KEY", "legacy"),
    ("OPENROUTER_API_KEY", "openrouter"),
    ("DOCPILOT_PROVIDER_DOMESTIC_API_KEY", "domestic"),
    ("ALIYUN_API_KEY", "domestic"),
    ("DASHSCOPE_API_KEY", "domestic"),
    ("DOCPILOT_PROVIDER_OPENAI_API_KEY", "openai"),
    ("OPENAI_API_KEY", "openai"),
)


def _first_present(names: tuple[tuple[str, str], ...]) -> tuple[str | None, str | None]:
    for name, family in names:
        value = os.environ.get(name)
        if value:
            return value, family
    return None, None


def _endpoint(base_url: str, suffix: str) -> str:
    return f"{base_url.rstrip('/')}/{suffix.lstrip('/')}"


def embedding_api_key() -> str | None:
    """Resolve the server-side API key without returning it from application APIs."""
    key, _family = _first_present(_EMBEDDING_KEY_SOURCES)
    return key


def embedding_provider_family() -> str | None:
    """Return only the active provider family for safe profile derivation."""
    _key, family = _first_present(_EMBEDDING_KEY_SOURCES)
    return family


def embedding_api_url(default_url: str) -> str:
    """Resolve a full OpenAI-compatible embeddings endpoint."""
    explicit_url = os.environ.get("EMBEDDING_API_URL")
    if explicit_url:
        return explicit_url

    _key, family = _first_present(_EMBEDDING_KEY_SOURCES)
    if family == "platform":
        base_url = os.environ.get("DOCPILOT_EMBEDDING_BASE_URL")
        if base_url:
            return _endpoint(base_url, "embeddings")
        return default_url
    if family == "domestic":
        base_url = os.environ.get("DOCPILOT_PROVIDER_DOMESTIC_BASE_URL", DASHSCOPE_BASE_URL)
        return _endpoint(base_url, "embeddings")
    if family == "openrouter":
        base_url = os.environ.get("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL)
        return _endpoint(base_url, "embeddings")
    if family == "openai":
        base_url = os.environ.get("DOCPILOT_PROVIDER_OPENAI_BASE_URL")
        if base_url:
            return _endpoint(base_url, "embeddings")
    return default_url


def embedding_model(default_model: str) -> str:
    """Resolve the active model using the same provider precedence as the worker."""
    explicit_model = os.environ.get("EMBEDDING_MODEL")
    if explicit_model:
        return explicit_model

    _key, family = _first_present(_EMBEDDING_KEY_SOURCES)
    if family == "platform":
        return os.environ.get("DOCPILOT_EMBEDDING_MODEL", default_model)
    if family == "domestic":
        return os.environ.get("DOCPILOT_EMBEDDING_MODEL_TEXT", DASHSCOPE_EMBEDDING_MODEL)
    if family == "openrouter":
        return os.environ.get("OPENROUTER_EMBEDDING_MODEL", OPENROUTER_EMBEDDING_MODEL)
    return default_model


def embedding_dimensions() -> int | None:
    """Return an explicit provider dimension request when one is configured."""
    explicit_dimensions = os.environ.get("EMBEDDING_DIMENSIONS") or os.environ.get(
        "DOCPILOT_EMBEDDING_DIMENSIONS"
    )
    if explicit_dimensions:
        return int(explicit_dimensions)

    _key, family = _first_present(_EMBEDDING_KEY_SOURCES)
    if family == "openrouter":
        return int(os.environ.get("OPENROUTER_EMBEDDING_DIMENSIONS", OPENROUTER_EMBEDDING_DIMENSIONS))
    return None


__all__ = [
    "DASHSCOPE_BASE_URL",
    "DASHSCOPE_EMBEDDING_MODEL",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_EMBEDDING_DIMENSIONS",
    "OPENROUTER_EMBEDDING_MODEL",
    "embedding_api_key",
    "embedding_api_url",
    "embedding_dimensions",
    "embedding_model",
    "embedding_provider_family",
]
