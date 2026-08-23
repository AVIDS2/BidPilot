"""Ephemeral live projections for queued Pi runs.

PostgreSQL RuntimeEvent remains the durable source of truth. Redis is only a
short-lived delivery path so the browser can see the Worker-owned Pi session
as it runs; reconnects fall back to the durable event cursor.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

import redis.asyncio as redis


logger = logging.getLogger(__name__)
_CHANNEL_PREFIX = "docpilot:assistant:live:"
_DEFAULT_TIMEOUT_SECONDS = 900.0


def _redis_url() -> str | None:
    value = os.getenv("DOCPILOT_REDIS_URL", "").strip()
    return value or None


def live_channel(run_id: str) -> str:
    return f"{_CHANNEL_PREFIX}{run_id}"


async def publish_live_frame(run_id: str, frame: str) -> None:
    """Best-effort publish of a user-safe SSE frame."""

    url = _redis_url()
    if not url or not frame:
        return
    client = redis.from_url(url, decode_responses=True)
    try:
        await client.publish(live_channel(run_id), frame)
    except Exception:  # noqa: BLE001 - live delivery must not fail the run
        logger.debug("Live assistant publish unavailable", exc_info=True)
    finally:
        await client.aclose()


def _timeout_seconds() -> float:
    try:
        value = float(os.getenv("DOCPILOT_ASSISTANT_LIVE_STREAM_TIMEOUT_SECONDS", str(_DEFAULT_TIMEOUT_SECONDS)))
    except ValueError:
        value = _DEFAULT_TIMEOUT_SECONDS
    return min(max(value, 30.0), 3600.0)


@dataclass
class LiveRunSubscription:
    client: redis.Redis
    pubsub: redis.client.PubSub
    deadline: float

    async def events(self) -> AsyncIterator[str]:
        while time.monotonic() < self.deadline:
            message = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                frame = message.get("data")
                if isinstance(frame, str) and frame:
                    yield frame
                    if "event: assistant.end" in frame:
                        return
            await asyncio.sleep(0.02)

    async def close(self) -> None:
        try:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        finally:
            await self.client.aclose()


@asynccontextmanager
async def open_live_run(run_id: str) -> AsyncIterator[LiveRunSubscription | None]:
    """Subscribe before queue dispatch to avoid losing the first Pi event."""

    url = _redis_url()
    if not url:
        yield None
        return
    client = redis.from_url(url, decode_responses=True)
    pubsub = client.pubsub()
    try:
        await pubsub.subscribe(live_channel(run_id))
        subscription = LiveRunSubscription(
            client=client,
            pubsub=pubsub,
            deadline=time.monotonic() + _timeout_seconds(),
        )
        try:
            yield subscription
        finally:
            await subscription.close()
    except Exception:  # noqa: BLE001 - durable polling remains available
        logger.debug("Live assistant subscription unavailable", exc_info=True)
        try:
            await pubsub.close()
        finally:
            await client.aclose()
        yield None


__all__ = ["live_channel", "open_live_run", "publish_live_frame"]
