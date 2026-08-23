from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from app.runtime import live_events


class _FakePubSub:
    def __init__(self, queues: dict[str, asyncio.Queue[dict[str, Any]]]) -> None:
        self._queues = queues
        self._channel = ""

    async def subscribe(self, channel: str) -> None:
        self._channel = channel

    async def get_message(self, *, ignore_subscribe_messages: bool, timeout: float) -> dict[str, Any] | None:
        try:
            return await asyncio.wait_for(self._queues[self._channel].get(), timeout=timeout)
        except TimeoutError:
            return None

    async def unsubscribe(self) -> None:
        return None

    async def close(self) -> None:
        return None


class _FakeRedis:
    queues: dict[str, asyncio.Queue[dict[str, Any]]] = defaultdict(asyncio.Queue)

    def pubsub(self) -> _FakePubSub:
        return _FakePubSub(self.queues)

    async def publish(self, channel: str, frame: str) -> None:
        await self.queues[channel].put({"type": "message", "data": frame})

    async def aclose(self) -> None:
        return None


def test_live_channel_delivers_pi_frame_without_using_durable_replay(monkeypatch) -> None:
    fake = _FakeRedis()
    monkeypatch.setenv("DOCPILOT_REDIS_URL", "redis://test")
    monkeypatch.setattr(live_events.redis, "from_url", lambda *_args, **_kwargs: fake)

    async def scenario() -> list[str]:
        async with live_events.open_live_run("run-live") as subscription:
            assert subscription is not None
            await live_events.publish_live_frame("run-live", "event: assistant.end\ndata: {}\n\n")
            return [frame async for frame in subscription.events()]

    frames = asyncio.run(scenario())
    assert frames == ["event: assistant.end\ndata: {}\n\n"]
