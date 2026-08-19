"""Shared hosted-environment policy for platform-funded model capacity.

The ledger stays reusable across API and Worker processes. This small module
only decides whether a server-owned official-model ceiling has been configured;
it never reads or exposes provider credentials.
"""

from __future__ import annotations

import os
from collections.abc import Mapping


OFFICIAL_MONTHLY_TOKEN_CEILING_ENV = "DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING"
INTERNAL_UNLIMITED_USAGE_ENV = "DOCPILOT_INTERNAL_UNLIMITED_USAGE"
HOSTED_ENVIRONMENTS = frozenset({"production", "staging"})


class OfficialTokenCeilingConfigurationError(ValueError):
    """Raised when hosted platform-funded AI has no safe token ceiling."""


def internal_unlimited_usage_enabled(
    environment: Mapping[str, str] | None = None,
) -> bool:
    """Return whether an explicitly configured internal test deployment is unmetered.

    This switch is intentionally narrow: callers may bypass product quotas and
    token-budget reservations, but authentication, tenant isolation, approval,
    audit, and provider credentials remain mandatory.
    """
    source = os.environ if environment is None else environment
    return source.get(INTERNAL_UNLIMITED_USAGE_ENV, "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def is_hosted_environment(environment: Mapping[str, str] | None = None) -> bool:
    source = os.environ if environment is None else environment
    return source.get("DOCPILOT_ENV", "local").strip().lower() in HOSTED_ENVIRONMENTS


def configured_official_monthly_token_ceiling(
    environment: Mapping[str, str] | None = None,
) -> int | None:
    """Parse the platform-funded monthly token ceiling without requiring it."""
    source = os.environ if environment is None else environment
    raw_value = source.get(OFFICIAL_MONTHLY_TOKEN_CEILING_ENV)
    if raw_value is None or not raw_value.strip():
        return None
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise OfficialTokenCeilingConfigurationError(
            f"{OFFICIAL_MONTHLY_TOKEN_CEILING_ENV} must be a non-negative integer"
        ) from exc
    if value < 0:
        raise OfficialTokenCeilingConfigurationError(
            f"{OFFICIAL_MONTHLY_TOKEN_CEILING_ENV} must be a non-negative integer"
        )
    return value


def require_official_monthly_token_ceiling(
    environment: Mapping[str, str] | None = None,
) -> int | None:
    """Require a ceiling in staging/production while keeping local development usable."""
    if internal_unlimited_usage_enabled(environment):
        return None
    value = configured_official_monthly_token_ceiling(environment)
    if value is None and is_hosted_environment(environment):
        raise OfficialTokenCeilingConfigurationError(
            f"{OFFICIAL_MONTHLY_TOKEN_CEILING_ENV} is required outside local development"
        )
    return value
