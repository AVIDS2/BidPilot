"""Normalize user-configured provider URLs.

Users often paste either a base URL (``https://api.deepseek.com``), a versioned
base URL (``https://api.deepseek.com/v1``), or a full endpoint. Internally we
keep two shapes explicit:

- endpoint URL: used by direct HTTP calls
- base URL: used by LangChain clients that append their own endpoint paths
"""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit, urlunsplit

ProviderProtocol = Literal["openai", "anthropic"]

_DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"


def normalize_provider_endpoint(provider_type: str, api_url: str | None) -> str:
    """Return a full HTTP endpoint for the selected protocol."""
    protocol = _normalize_protocol(provider_type)
    base_url = normalize_provider_base_url(protocol, api_url)
    if protocol == "anthropic":
        return f"{base_url}/v1/messages"
    return f"{base_url}/chat/completions"


def normalize_provider_base_url(provider_type: str, api_url: str | None) -> str:
    """Return a LangChain/client base URL for the selected protocol."""
    protocol = _normalize_protocol(provider_type)
    if not api_url or not api_url.strip():
        return _DEFAULT_ANTHROPIC_BASE_URL if protocol == "anthropic" else _DEFAULT_OPENAI_BASE_URL

    url = _strip_trailing_slashes(api_url.strip())
    if protocol == "anthropic":
        return _normalize_anthropic_base_url(url)
    return _normalize_openai_base_url(url)


def _normalize_protocol(provider_type: str) -> ProviderProtocol:
    return "anthropic" if provider_type == "anthropic" else "openai"


def _normalize_openai_base_url(url: str) -> str:
    url = _strip_known_suffix(url, "/chat/completions")
    if _path_ends_with(url, "/v1"):
        return url
    return f"{url}/v1"


def _normalize_anthropic_base_url(url: str) -> str:
    url = _strip_known_suffix(url, "/messages")
    url = _strip_known_suffix(url, "/v1")
    return url


def _strip_known_suffix(url: str, suffix: str) -> str:
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    if path.endswith(suffix):
        path = path[: -len(suffix)].rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment)).rstrip("/")


def _path_ends_with(url: str, suffix: str) -> bool:
    return urlsplit(url).path.rstrip("/").endswith(suffix)


def _strip_trailing_slashes(url: str) -> str:
    return url.rstrip("/")
