from __future__ import annotations

import asyncio

import pytest

from app.assistant.router import _with_sse_heartbeats


@pytest.mark.anyio
async def test_assistant_stream_emits_a_heartbeat_without_cancelling_the_source() -> None:
    release = asyncio.Event()

    async def slow_stream():
        await release.wait()
        yield "event: assistant.end\ndata: {}\n\n"

    stream = _with_sse_heartbeats(slow_stream(), heartbeat_seconds=0.001)
    assert await anext(stream) == ": keep-alive\n\n"

    release.set()
    assert await anext(stream) == "event: assistant.end\ndata: {}\n\n"
    await stream.aclose()
