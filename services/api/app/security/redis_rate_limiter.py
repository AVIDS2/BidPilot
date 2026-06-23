"""Redis-backed rate limiter with in-memory fallback."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Protocol

logger = logging.getLogger(__name__)


class RateLimiterBackend(Protocol):
    def check(self, key: str) -> None: ...
    def reset(self, key: str) -> None: ...


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
            raise ValueError(f"Too many {self.label} attempts. Please try again in {self.window_seconds // 60} minutes.")
        self._attempts[key].append(now)

    def reset(self, key: str) -> None:
        self._attempts.pop(key, None)


class RedisRateLimiter:
    """Redis-backed sliding window rate limiter using INCR + EXPIRE."""

    def __init__(self, redis_client, max_attempts: int, window_seconds: int, prefix: str, label: str = "request") -> None:
        self._redis = redis_client
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.prefix = prefix
        self.label = label

    def _key(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    def check(self, key: str) -> None:
        redis_key = self._key(key)
        try:
            count = self._redis.incr(redis_key)
            if count == 1:
                self._redis.expire(redis_key, self.window_seconds)
            if count > self.max_attempts:
                raise ValueError(f"Too many {self.label} attempts. Please try again in {self.window_seconds // 60} minutes.")
        except ValueError:
            raise
        except Exception:
            logger.warning("Redis rate limiter failed, allowing request")

    def reset(self, key: str) -> None:
        try:
            self._redis.delete(self._key(key))
        except Exception:
            logger.warning("Redis rate limiter reset failed")


def create_rate_limiter(
    redis_url: str | None,
    max_attempts: int,
    window_seconds: int,
    prefix: str,
    label: str = "request",
) -> RateLimiterBackend:
    """Factory: use Redis if available, fall back to in-memory."""
    if redis_url:
        try:
            import redis

            client = redis.from_url(redis_url, decode_responses=True)
            client.ping()
            logger.info("Using Redis rate limiter (prefix=%s)", prefix)
            return RedisRateLimiter(client, max_attempts, window_seconds, prefix, label)
        except Exception as exc:
            logger.warning("Redis unavailable (%s), falling back to in-memory rate limiter", exc)
    return InMemoryRateLimiter(max_attempts, window_seconds, label)
