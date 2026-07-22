"""Global API rate limiting with Redis in production and safe failure modes."""

from __future__ import annotations

import os
from collections.abc import Mapping

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.security.client_identity import (
    get_client_identity_fingerprint,
    require_trusted_proxy_configuration,
)
from app.security.redis_rate_limiter import (
    RateLimitExceeded,
    RateLimiterBackend,
    RateLimiterUnavailable,
    create_rate_limiter,
)


DEFAULT_API_RATE_LIMIT = "1000/minute"
RATE_LIMIT_STORAGE_URI_ENV = "DOCPILOT_RATE_LIMIT_STORAGE_URI"
RATE_LIMIT_ENV = "DOCPILOT_RATE_LIMIT"
_WINDOW_SECONDS = {
    "second": 1,
    "seconds": 1,
    "minute": 60,
    "minutes": 60,
    "hour": 60 * 60,
    "hours": 60 * 60,
    "day": 24 * 60 * 60,
    "days": 24 * 60 * 60,
}


class ApiRateLimitConfigurationError(ValueError):
    """The configured public API rate limit is malformed."""


def parse_api_rate_limit(value: str) -> tuple[int, int]:
    """Parse a compact fixed-window budget such as ``1000/minute``."""
    parts = value.strip().lower().split("/")
    if len(parts) != 2:
        raise ApiRateLimitConfigurationError(
            f"{RATE_LIMIT_ENV} must use the form '<positive integer>/<second|minute|hour|day>'"
        )
    raw_count, raw_window = parts
    try:
        count = int(raw_count)
    except ValueError:
        raise ApiRateLimitConfigurationError(f"{RATE_LIMIT_ENV} must start with a positive integer") from None
    window_seconds = _WINDOW_SECONDS.get(raw_window)
    if count <= 0 or window_seconds is None:
        raise ApiRateLimitConfigurationError(
            f"{RATE_LIMIT_ENV} must use a positive count and a supported time window"
        )
    return count, window_seconds


def create_api_rate_limiter(
    environment: Mapping[str, str] | None = None,
) -> RateLimiterBackend:
    """Create the global limiter, requiring Redis and trusted proxy config in production."""
    source = os.environ if environment is None else environment
    max_requests, window_seconds = parse_api_rate_limit(
        source.get(RATE_LIMIT_ENV, DEFAULT_API_RATE_LIMIT)
    )
    is_production = source.get("DOCPILOT_ENV", "").lower() == "production"
    if is_production:
        require_trusted_proxy_configuration(source)

    storage_uri = source.get(RATE_LIMIT_STORAGE_URI_ENV) or source.get("DOCPILOT_REDIS_URL")
    return create_rate_limiter(
        redis_url=storage_uri,
        max_attempts=max_requests,
        window_seconds=window_seconds,
        prefix="docpilot:rate-limit:api",
        label="API request",
        require_redis=is_production,
    )


def _hashed_client_key(request: Request) -> str:
    return get_client_identity_fingerprint(request)


class GlobalApiRateLimitMiddleware(BaseHTTPMiddleware):
    """Apply one per-client fixed-window budget to every public API request."""

    def __init__(self, app, *, limiter: RateLimiterBackend) -> None:
        super().__init__(app)
        self._limiter = limiter

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Liveness must stay independent from Redis so an orchestrator can tell
        # a live process apart from one that is temporarily not ready.
        if request.url.path == "/health":
            return await call_next(request)
        try:
            self._limiter.check(_hashed_client_key(request))
        except RateLimitExceeded:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "message": "Too many requests. Please try again later.",
                    "details": None,
                },
            )
        except RateLimiterUnavailable:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "rate_limit_unavailable",
                    "message": "Request protection is temporarily unavailable.",
                    "details": None,
                },
            )
        return await call_next(request)
