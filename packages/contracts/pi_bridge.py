"""Shared, dependency-light authentication for the Pi tool bridge."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt


def encode_pi_bridge_token(
    *,
    run_id: str,
    user_id: str,
    org_id: str,
    email: str,
    display_name: str,
    role: str,
    plan: str,
    org_slug: str,
    memory_enabled: bool = True,
    secret: str,
    ttl_seconds: int = 300,
) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "purpose": "pi-tool-bridge",
            "run_id": run_id,
            "user_id": user_id,
            "org_id": org_id,
            "email": email,
            "display_name": display_name,
            "role": role,
            "plan": plan,
            "org_slug": org_slug,
            "memory_enabled": memory_enabled,
            "exp": now + timedelta(seconds=ttl_seconds),
            "iat": now,
        },
        secret,
        algorithm="HS256",
    )


def encode_agent_wake_token(
    *,
    wake_run_id: str,
    secret: str,
    ttl_seconds: int = 300,
) -> str:
    """Authorize one worker-originated, idempotent Agent continuation."""
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "purpose": "agent-system-wake",
            "wake_run_id": wake_run_id,
            "exp": now + timedelta(seconds=ttl_seconds),
            "iat": now,
        },
        secret,
        algorithm="HS256",
    )


def encode_assistant_task_token(
    *,
    run_id: str,
    user_id: str,
    org_id: str,
    secret: str,
    ttl_seconds: int = 900,
) -> str:
    """Authorize a Worker to start one queued assistant runtime run."""

    now = datetime.now(UTC)
    return jwt.encode(
        {
            "purpose": "assistant-task",
            "run_id": run_id,
            "user_id": user_id,
            "org_id": org_id,
            "exp": now + timedelta(seconds=ttl_seconds),
            "iat": now,
        },
        secret,
        algorithm="HS256",
    )


__all__ = ["encode_agent_wake_token", "encode_assistant_task_token", "encode_pi_bridge_token"]
