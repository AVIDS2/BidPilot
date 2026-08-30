"""Internal control calls for the Pi sidecar."""

from __future__ import annotations

import asyncio
import logging
import os
from urllib.parse import quote
from typing import Any

import httpx


logger = logging.getLogger(__name__)
_active_pi_executions: dict[str, asyncio.Task[Any]] = {}


def register_pi_execution(run_id: str, task: asyncio.Task[Any]) -> None:
    """Track the local API task that is awaiting one Worker Pi execution."""

    _active_pi_executions[run_id] = task


def unregister_pi_execution(run_id: str, task: asyncio.Task[Any]) -> None:
    if _active_pi_executions.get(run_id) is task:
        _active_pi_executions.pop(run_id, None)


def cancel_active_pi_execution(run_id: str) -> bool:
    """Interrupt a same-process Worker request after durable cancellation."""

    task = _active_pi_executions.get(run_id)
    if task is None or task.done():
        return False
    task.cancel()
    return True


async def request_pi_abort(run_id: str) -> bool:
    """Ask the active Pi AgentSession to abort through its official API."""

    sidecar_url = os.getenv("DOCPILOT_PI_AGENT_URL", "http://pi-agent:8787").rstrip("/")
    secret = (os.getenv("DOCPILOT_PI_INTERNAL_SECRET") or os.getenv("DOCPILOT_JWT_SECRET") or "").strip()
    if not secret:
        logger.error("Pi abort skipped because the internal secret is unavailable")
        return False

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(
                f"{sidecar_url}/v1/runs/{quote(run_id, safe='')}/abort",
                headers={"authorization": f"Bearer {secret}"},
            )
    except httpx.HTTPError:
        logger.warning("Pi abort request could not reach the sidecar", extra={"run_id": run_id})
        return False

    if response.status_code in {202, 404}:
        # 404 means the run was queued or has already left the sidecar. The
        # durable cancellation state remains authoritative in either case.
        logger.info(
            "Pi abort accepted",
            extra={"run_id": run_id, "sidecar_url": sidecar_url, "status_code": response.status_code},
        )
        return True
    logger.warning(
        "Pi abort request was rejected",
        extra={"run_id": run_id, "status_code": response.status_code},
    )
    return False


__all__ = [
    "cancel_active_pi_execution",
    "register_pi_execution",
    "request_pi_abort",
    "unregister_pi_execution",
]
