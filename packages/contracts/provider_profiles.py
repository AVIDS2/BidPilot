"""Shared provider protocol profiles for API and worker runtimes.

The registry holds only public integration metadata. API keys remain owned by
the API service and are never persisted or logged from this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

ProviderProtocol = Literal["openai", "anthropic"]
AuthScheme = Literal["bearer", "anthropic", "api-key"]
ModelDiscoveryMode = Literal["supported", "manual", "best_effort"]


class ProviderProfileError(ValueError):
    """Raised when a saved provider profile cannot form a safe request."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ProviderProfile:
    """Public transport behavior for a known provider or custom gateway."""

    id: str
    protocol: ProviderProtocol
    auth_scheme: AuthScheme
    default_base_url: str | None
    default_model: str
    docs_url: str | None
    model_discovery: ModelDiscoveryMode = "best_effort"
    model_list_protocol: ProviderProtocol | None = None
    model_list_base_url: str | None = None
    model_list_auth_scheme: AuthScheme | None = None
    requires_api_url: bool = False


@dataclass(frozen=True)
class ProviderRequest:
    """A fully resolved endpoint and safe request headers."""

    url: str
    headers: dict[str, str]
    profile: ProviderProfile


_DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
_OPENAI_ENDPOINT_SUFFIXES = (
    "/chat/completions",
    "/responses",
    "/models",
    "/completions",
    "/embeddings",
)
_BARE_OPENAI_COMPATIBLE_HOSTS_WITHOUT_VERSION = {
    "api.deepseek.com",
}


PROVIDER_PROFILES: dict[str, ProviderProfile] = {
    "custom-openai": ProviderProfile(
        id="custom-openai",
        protocol="openai",
        auth_scheme="bearer",
        default_base_url=_DEFAULT_OPENAI_BASE_URL,
        default_model="gpt-4o",
        docs_url=None,
        model_discovery="best_effort",
    ),
    "openai": ProviderProfile(
        id="openai",
        protocol="openai",
        auth_scheme="bearer",
        default_base_url=_DEFAULT_OPENAI_BASE_URL,
        default_model="gpt-4o",
        docs_url="https://platform.openai.com/docs/api-reference/models/list",
        model_discovery="supported",
    ),
    "deepseek": ProviderProfile(
        id="deepseek",
        protocol="openai",
        auth_scheme="bearer",
        default_base_url="https://api.deepseek.com",
        default_model="deepseek-v4-flash",
        docs_url="https://api-docs.deepseek.com/api/list-models",
        model_discovery="supported",
    ),
    "deepseek-anthropic": ProviderProfile(
        id="deepseek-anthropic",
        protocol="anthropic",
        auth_scheme="anthropic",
        default_base_url="https://api.deepseek.com/anthropic",
        default_model="deepseek-v4-flash",
        docs_url="https://api-docs.deepseek.com/guides/anthropic_api",
        model_discovery="supported",
        model_list_protocol="openai",
        model_list_base_url="https://api.deepseek.com",
        model_list_auth_scheme="bearer",
    ),
    "dashscope": ProviderProfile(
        id="dashscope",
        protocol="openai",
        auth_scheme="bearer",
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="qwen-plus",
        docs_url="https://help.aliyun.com/en/model-studio/compatibility-of-openai-with-dashscope",
        model_discovery="manual",
    ),
    "doubao": ProviderProfile(
        id="doubao",
        protocol="openai",
        auth_scheme="bearer",
        default_base_url="https://ark.cn-beijing.volces.com/api/v3",
        default_model="ep-xxxxxxxx",
        docs_url="https://www.volcengine.com/docs/82379",
        model_discovery="manual",
    ),
    "anthropic": ProviderProfile(
        id="anthropic",
        protocol="anthropic",
        auth_scheme="anthropic",
        default_base_url=_DEFAULT_ANTHROPIC_BASE_URL,
        default_model="claude-sonnet-4-20250514",
        docs_url="https://docs.anthropic.com/en/api/models",
        model_discovery="supported",
    ),
    "zhipu": ProviderProfile(
        id="zhipu",
        protocol="openai",
        auth_scheme="bearer",
        default_base_url="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-4-flash",
        docs_url="https://docs.bigmodel.cn/cn/guide/develop/openai/introduction",
        model_discovery="manual",
    ),
    "minimax": ProviderProfile(
        id="minimax",
        protocol="openai",
        auth_scheme="bearer",
        default_base_url="https://api.minimax.io/v1",
        default_model="MiniMax-M3",
        docs_url="https://platform.minimaxi.com/document/models",
        model_discovery="manual",
    ),
    "siliconflow": ProviderProfile(
        id="siliconflow",
        protocol="openai",
        auth_scheme="bearer",
        default_base_url="https://api.siliconflow.cn/v1",
        default_model="deepseek-ai/DeepSeek-V3",
        docs_url="https://docs.siliconflow.cn/en/api-reference/models/get-model-list",
        model_discovery="supported",
    ),
    "openrouter": ProviderProfile(
        id="openrouter",
        protocol="openai",
        auth_scheme="bearer",
        default_base_url="https://openrouter.ai/api/v1",
        default_model="openai/gpt-4o-mini",
        docs_url="https://openrouter.ai/docs/api-reference/models/get-models",
        model_discovery="supported",
    ),
    "mimo": ProviderProfile(
        id="mimo",
        protocol="openai",
        auth_scheme="api-key",
        default_base_url=None,
        default_model="mimo-v2.5-pro",
        docs_url="https://mimo.mi.com/docs/en-US/tokenplan/Token%20Plan/quick-access",
        model_discovery="manual",
        requires_api_url=True,
    ),
    "custom-anthropic": ProviderProfile(
        id="custom-anthropic",
        protocol="anthropic",
        auth_scheme="anthropic",
        default_base_url=_DEFAULT_ANTHROPIC_BASE_URL,
        default_model="claude-sonnet-4-20250514",
        docs_url=None,
        model_discovery="best_effort",
    ),
}


def default_provider_id(protocol: str) -> str:
    return "custom-anthropic" if protocol == "anthropic" else "custom-openai"


def get_provider_profile(provider_id: str | None, protocol: str) -> ProviderProfile:
    """Return a profile validated against the selected transport protocol."""
    normalized_protocol = normalize_provider_protocol(protocol)
    resolved_id = provider_id or default_provider_id(normalized_protocol)
    profile = PROVIDER_PROFILES.get(resolved_id)
    if profile is None:
        raise ProviderProfileError("provider_profile_invalid", "Unknown provider profile")
    if profile.protocol != normalized_protocol:
        # A historical ORM default may predate the provider_id column. It is
        # safe to map only the generic default to the equivalent protocol.
        if resolved_id == "custom-openai" and normalized_protocol == "anthropic":
            return PROVIDER_PROFILES["custom-anthropic"]
        raise ProviderProfileError("provider_profile_invalid", "Provider profile does not match the selected protocol")
    return profile


def infer_provider_id(protocol: str, api_url: str | None) -> str:
    """Backfill a profile ID from a public host while preserving custom URLs."""
    normalized_protocol = normalize_provider_protocol(protocol)
    value = (api_url or "").lower()
    if normalized_protocol == "anthropic" and "api.deepseek.com/anthropic" in value:
        return "deepseek-anthropic"
    if "api.openai.com" in value:
        return "openai"
    if "api.deepseek.com" in value:
        return "deepseek"
    if "dashscope.aliyuncs.com" in value:
        return "dashscope"
    if "ark.cn-beijing.volces.com" in value:
        return "doubao"
    if "api.anthropic.com" in value:
        return "anthropic"
    if "bigmodel.cn" in value:
        return "zhipu"
    if "minimax" in value:
        return "minimax"
    if "siliconflow.cn" in value:
        return "siliconflow"
    if "openrouter.ai" in value:
        return "openrouter"
    if "xiaomimimo.com" in value:
        return "mimo"
    return default_provider_id(normalized_protocol)


def normalize_provider_protocol(provider_type: str) -> ProviderProtocol:
    return "anthropic" if provider_type == "anthropic" else "openai"


def normalize_provider_base_url(
    provider_type: str,
    api_url: str | None,
    provider_id: str | None = None,
) -> str:
    """Return a client base URL from either a base URL or full endpoint."""
    protocol = normalize_provider_protocol(provider_type)
    profile = get_provider_profile(provider_id, protocol)
    raw_url = (api_url or "").strip() or profile.default_base_url
    if not raw_url:
        raise ProviderProfileError(
            "provider_endpoint_required",
            "This provider requires the base URL shown in its provider console",
        )

    url = _strip_trailing_slashes(raw_url)
    if protocol == "anthropic":
        return _normalize_anthropic_base_url(url)
    return _normalize_openai_base_url(url)


def normalize_provider_endpoint(
    provider_type: str,
    api_url: str | None,
    provider_id: str | None = None,
) -> str:
    """Return the complete chat endpoint for a selected provider profile."""
    protocol = normalize_provider_protocol(provider_type)
    base_url = normalize_provider_base_url(protocol, api_url, provider_id)
    if protocol == "anthropic":
        return f"{base_url}/v1/messages"
    return f"{base_url}/chat/completions"


def resolve_provider_chat_request(
    provider_type: str,
    provider_id: str | None,
    api_url: str | None,
    api_key: str,
) -> ProviderRequest:
    """Resolve the exact chat URL and headers used by every direct adapter."""
    protocol = normalize_provider_protocol(provider_type)
    profile = get_provider_profile(provider_id, protocol)
    return ProviderRequest(
        url=normalize_provider_endpoint(protocol, api_url, profile.id),
        headers=provider_request_headers(profile, api_key),
        profile=profile,
    )


def resolve_provider_model_list_request(
    provider_type: str,
    provider_id: str | None,
    api_url: str | None,
    api_key: str,
) -> ProviderRequest | None:
    """Resolve a documented model-list request or return None for manual profiles."""
    protocol = normalize_provider_protocol(provider_type)
    profile = get_provider_profile(provider_id, protocol)
    if profile.model_discovery == "manual":
        return None

    list_protocol = profile.model_list_protocol or profile.protocol
    list_base_url = profile.model_list_base_url or api_url
    base_url = normalize_provider_base_url(list_protocol, list_base_url, _profile_for_protocol(profile, list_protocol))
    url = f"{base_url}/v1/models" if list_protocol == "anthropic" else f"{base_url}/models"
    headers = provider_request_headers(
        profile,
        api_key,
        auth_scheme=profile.model_list_auth_scheme,
        include_content_type=False,
    )
    return ProviderRequest(url=url, headers=headers, profile=profile)


def provider_request_headers(
    profile: ProviderProfile,
    api_key: str,
    *,
    auth_scheme: AuthScheme | None = None,
    include_content_type: bool = True,
) -> dict[str, str]:
    """Return profile-specific headers without logging the secret value."""
    scheme = auth_scheme or profile.auth_scheme
    if scheme == "api-key":
        headers = {"api-key": api_key}
    elif scheme == "anthropic":
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
    else:
        headers = {"Authorization": f"Bearer {api_key}"}
    if include_content_type:
        headers["content-type"] = "application/json"
    return headers


def profile_client_headers(provider_type: str, provider_id: str | None, api_key: str) -> dict[str, str]:
    """Return headers required in addition to standard LangChain client auth."""
    profile = get_provider_profile(provider_id, provider_type)
    headers = provider_request_headers(profile, api_key, include_content_type=False)
    if profile.auth_scheme == "bearer":
        return {}
    return headers


def _profile_for_protocol(profile: ProviderProfile, protocol: ProviderProtocol) -> str:
    """Choose a compatible normalizer profile for an overridden list protocol."""
    if profile.protocol == protocol:
        return profile.id
    return default_provider_id(protocol)


def _normalize_openai_base_url(url: str) -> str:
    url = _strip_known_suffixes(url, _OPENAI_ENDPOINT_SUFFIXES)
    if _has_no_path(url):
        hostname = urlsplit(url).hostname or ""
        if hostname.lower() in _BARE_OPENAI_COMPATIBLE_HOSTS_WITHOUT_VERSION:
            return url
        return _append_path(url, "/v1")
    if _path_ends_with(url, "/v1"):
        return url
    if _path_ends_with_version_segment(url):
        return url
    return f"{url}/v1"


def _normalize_anthropic_base_url(url: str) -> str:
    url = _strip_known_suffix(url, "/models")
    url = _strip_known_suffix(url, "/messages")
    url = _strip_known_suffix(url, "/v1")
    return url


def _strip_known_suffixes(url: str, suffixes: tuple[str, ...]) -> str:
    normalized = url
    for suffix in suffixes:
        normalized = _strip_known_suffix(normalized, suffix)
    return normalized


def _strip_known_suffix(url: str, suffix: str) -> str:
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    if path.endswith(suffix):
        path = path[: -len(suffix)].rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment)).rstrip("/")


def _path_ends_with(url: str, suffix: str) -> bool:
    return urlsplit(url).path.rstrip("/").endswith(suffix)


def _path_ends_with_version_segment(url: str) -> bool:
    path = urlsplit(url).path.rstrip("/")
    return bool(re.search(r"(^|/)v\d+$", path))


def _has_no_path(url: str) -> bool:
    return urlsplit(url).path.rstrip("/") == ""


def _append_path(url: str, suffix: str) -> str:
    parts = urlsplit(url)
    path = f"{parts.path.rstrip('/')}{suffix}"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment)).rstrip("/")


def _strip_trailing_slashes(url: str) -> str:
    return url.rstrip("/")
