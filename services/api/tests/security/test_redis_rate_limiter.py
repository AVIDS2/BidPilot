import pytest

from app.security.redis_rate_limiter import (
    RateLimitExceeded,
    RateLimiterUnavailable,
    RedisRateLimiter,
    create_rate_limiter,
)


class _ScriptedRedis:
    def __init__(self, responses: list[int] | None = None, error: Exception | None = None) -> None:
        self.responses = responses or []
        self.error = error
        self.calls: list[tuple[object, ...]] = []

    def eval(self, *args: object) -> int:
        self.calls.append(args)
        if self.error is not None:
            raise self.error
        return self.responses.pop(0)

    def delete(self, *_args: object) -> None:
        return None


def test_redis_rate_limiter_sets_an_atomic_expiring_counter() -> None:
    redis = _ScriptedRedis(responses=[1, 2, 3])
    limiter = RedisRateLimiter(
        redis,
        max_attempts=2,
        window_seconds=60,
        prefix="rl:test",
        label="test",
    )

    limiter.check("safe-key")
    limiter.check("safe-key")
    with pytest.raises(RateLimitExceeded):
        limiter.check("safe-key")

    script, num_keys, key, window_seconds = redis.calls[0]
    assert "EXPIRE" in str(script)
    assert num_keys == 1
    assert key == "rl:test:safe-key"
    assert window_seconds == 60


def test_redis_rate_limiter_fails_open_only_when_explicitly_non_production() -> None:
    limiter = RedisRateLimiter(
        _ScriptedRedis(error=OSError("redis unavailable")),
        max_attempts=2,
        window_seconds=60,
        prefix="rl:test",
    )

    limiter.check("safe-key")


def test_redis_rate_limiter_fails_closed_when_required() -> None:
    limiter = RedisRateLimiter(
        _ScriptedRedis(error=OSError("redis unavailable")),
        max_attempts=2,
        window_seconds=60,
        prefix="rl:test",
        fail_closed=True,
    )

    with pytest.raises(RateLimiterUnavailable):
        limiter.check("safe-key")


def test_factory_refuses_missing_redis_when_distributed_limit_is_required() -> None:
    with pytest.raises(RateLimiterUnavailable):
        create_rate_limiter(
            None,
            max_attempts=2,
            window_seconds=60,
            prefix="rl:test",
            require_redis=True,
        )
