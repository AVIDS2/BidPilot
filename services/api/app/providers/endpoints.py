"""Backward-compatible imports for shared provider URL resolution.

The API and Worker must resolve configured provider URLs through one common
contract. Keep this module so existing API callers and tests retain their
imports while the implementation lives in ``contracts``.
"""

from contracts.provider_profiles import (
    ProviderProfile,
    ProviderProfileError,
    ProviderRequest,
    get_provider_profile,
    infer_provider_id,
    normalize_provider_base_url,
    normalize_provider_endpoint,
    profile_client_headers,
    provider_request_headers,
    resolve_provider_chat_request,
    resolve_provider_model_list_request,
)

__all__ = [
    "ProviderProfile",
    "ProviderProfileError",
    "ProviderRequest",
    "get_provider_profile",
    "infer_provider_id",
    "normalize_provider_base_url",
    "normalize_provider_endpoint",
    "profile_client_headers",
    "provider_request_headers",
    "resolve_provider_chat_request",
    "resolve_provider_model_list_request",
]
