"""Redis-backed rate limiting with a controlled development fallback."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Protocol

logger = logging.getLogger(__name__)


class RateLimiterBackend(Protocol):
    def check(self, key: str) -> None: ...
    def reset(self, key: str) -> None: ...


class RateLimitExceeded(ValueError):
    """The caller exceeded a configured request budget."""


class RateLimiterUnavailable(RuntimeError):
    """A fail-closed limiter cannot verify a request safely."""


class InMemoryRateLimiter:
    """Fallback rate limiter when Redis is unavailable."""

    def __init__(self, max_attempts: int, window_seconds: int, label: str = "request") -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.label = label
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        self._attempts[key] = [t for t in self._attempts[key] if t > cutoff]
        if len(self._attempts[key]) >= self.max_attempts:
            raise RateLimitExceeded(
                f"Too many {self.label} attempts. Please try again in {self.window_seconds // 60} minutes."
            )
        self._attempts[key].append(now)

    def reset(self, key: str) -> None:
        self._attempts.pop(key, None)


class RedisRateLimiter:
    """Redis-backed fixed-window limiter with explicit runtime failure handling."""

    def __init__(
        self,
        redis_client,
        max_attempts: int,
        window_seconds: int,
        prefix: str,
        label: str = "request",
        *,
        fail_closed: bool = False,
    ) -> None:
        self._redis = redis_client
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.prefix = prefix
        self.label = label
        self.fail_closed = fail_closed

    def _key(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    def check(self, key: str) -> None:
        redis_key = self._key(key)
        try:
            # The script makes increment-and-expiry atomic, avoiding a permanent
            # counter if a process exits between separate INCR and EXPIRE calls.
            count = int(
                self._redis.eval(
                    "local count = redis.call('INCR', KEYS[1]); "
                    "if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]); end; "
                    "return count;",
                    1,
                    redis_key,
                    self.window_seconds,
                )
            )
        except Exception:
            if self.fail_closed:
                logger.error("Required Redis rate limiter check failed for %s", self.label)
                raise RateLimiterUnavailable("Authentication protection is temporarily unavailable") from None
            logger.warning("Redis rate limiter check failed for %s; allowing non-production request", self.label)
            return
        if count > self.max_attempts:
            raise RateLimitExceeded(
                f"Too many {self.label} attempts. Please try again in {self.window_seconds // 60} minutes."
            )

    def reset(self, key: str) -> None:
        try:
            self._redis.delete(self._key(key))
        except Exception:
            logger.warning("Redis rate limiter reset failed for %s", self.label)


def create_rate_limiter(
    redis_url: str | None,
    max_attempts: int,
    window_seconds: int,
    prefix: str,
    label: str = "request",
    *,
    require_redis: bool = False,
) -> RateLimiterBackend:
    """Use Redis in deployed environments and allow fallback only when permitted."""
    if redis_url:
        try:
            import redis

            client = redis.from_url(redis_url, decode_responses=True)
            client.ping()
            logger.info("Using Redis rate limiter (prefix=%s)", prefix)
            return RedisRateLimiter(
                client,
                max_attempts,
                window_seconds,
                prefix,
                label,
                fail_closed=require_redis,
            )
        except Exception:
            if require_redis:
                logger.error("Required Redis rate limiter is unavailable during startup")
                raise RateLimiterUnavailable("Required Redis rate limiter is unavailable") from None
            logger.warning("Redis rate limiter is unavailable; using in-memory limiter for non-production")
    elif require_redis:
        raise RateLimiterUnavailable("Required Redis rate limiter is not configured")
    return InMemoryRateLimiter(max_attempts, window_seconds, label)
