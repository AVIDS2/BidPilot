"""Internal tool bridge for the Pi sidecar.

The sidecar is deliberately not given database credentials or a user session.
Every tool call returns through this endpoint, where the existing BidPilot
policy, approval, idempotency and audit boundaries remain authoritative.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
from typing import Any

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.db import SessionLocal
from app.models import RuntimeRun
from .bidpilot_harness_adapter import BidPilotToolExecutor
from .harness_core import HarnessExecutionContext, HarnessToolCall
from .harness_loop import _TOOL_PARAMETER_SCHEMAS
from .registry import CAPABILITY_REGISTRY


router = APIRouter(prefix="/internal/pi", tags=["internal-pi"])
_ALGORITHM = "HS256"
_TOKEN_TTL_SECONDS = 300


class PiBridgeToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, max_length=64)
    tool_call_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=160)
    arguments: dict[str, Any] = Field(default_factory=dict)
    turn_id: str | None = Field(default=None, max_length=160)
    step: int = Field(default=1, ge=1, le=100)


def _secret() -> str:
    # In production the deployment must provide a dedicated secret. Falling
    # back to the JWT secret keeps local compose/dev usable without creating a
    # second credential, while never placing a secret in source or responses.
    value = os.getenv("DOCPILOT_PI_INTERNAL_SECRET") or os.getenv("DOCPILOT_JWT_SECRET")
    if not value:
        raise RuntimeError("DOCPILOT_PI_INTERNAL_SECRET is not configured")
    return value


def create_pi_bridge_token(*, run: RuntimeRun, user: CurrentUser) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "purpose": "pi-tool-bridge",
            "run_id": run.id,
            "user_id": user.id,
            "org_id": user.org_id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "plan": user.plan,
            "org_slug": user.org_slug,
            "exp": now + timedelta(seconds=_TOKEN_TTL_SECONDS),
            "iat": now,
        },
        _secret(),
        algorithm=_ALGORITHM,
    )


def _decode_token(authorization: str | None) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Pi bridge authorization required")
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
    except (jwt.PyJWTError, RuntimeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid Pi bridge authorization") from exc
    if claims.get("purpose") != "pi-tool-bridge":
        raise HTTPException(status_code=401, detail="Invalid Pi bridge purpose")
    return claims


def _user_from_claims(claims: dict[str, Any]) -> CurrentUser:
    return CurrentUser(
        id=str(claims["user_id"]),
        email=str(claims.get("email") or ""),
        display_name=str(claims.get("display_name") or ""),
        role=str(claims.get("role") or "member"),
        plan=str(claims.get("plan") or "starter"),
        org_id=str(claims["org_id"]),
        org_slug=str(claims.get("org_slug") or ""),
        email_verified=True,
    )


def _outcome_payload(outcome: Any) -> dict[str, Any]:
    return {
        "kind": str(outcome.kind.value if hasattr(outcome.kind, "value") else outcome.kind),
        "publicSummary": outcome.public_summary,
        "modelPayload": outcome.model_payload,
        "publicPayload": outcome.public_payload,
        "errorCode": outcome.error_code,
        "pauseReason": outcome.pause_reason,
        "recoverable": outcome.recoverable,
    }


@router.post("/tools/execute")
def execute_pi_tool(
    payload: PiBridgeToolCall,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    claims = _decode_token(authorization)
    if claims.get("run_id") != payload.run_id:
        raise HTTPException(status_code=403, detail="Pi bridge run scope mismatch")

    db: Session = SessionLocal()
    try:
        run = db.get(RuntimeRun, payload.run_id)
        if run is None or run.user_id != claims.get("user_id") or run.org_id != claims.get("org_id"):
            raise HTTPException(status_code=404, detail="Runtime run not found")
        if run.status not in {"running", "awaiting_approval"}:
            raise HTTPException(status_code=409, detail="Runtime run is no longer executable")

        user = _user_from_claims(claims)
        call = HarnessToolCall(
            id=payload.tool_call_id,
            name=payload.name,
            arguments=payload.arguments,
        )
        context = HarnessExecutionContext(
            run_id=payload.run_id,
            turn_id=payload.turn_id or f"pi-turn-{payload.step}",
            step=payload.step,
            completed_tool_names=(),
            failed_tool_names=(),
        )
        executor = BidPilotToolExecutor(
            db=db,
            user=user,
            runtime_run=run,
            conversation_id=run.conversation_id or "",
            parameter_schemas=_TOOL_PARAMETER_SCHEMAS,
            allowed_capabilities=frozenset(CAPABILITY_REGISTRY),
            active_project_id=run.project_id,
            provider_config_id=run.provider_config_id,
            reasoning_effort=run.reasoning_effort,
        )

        import asyncio

        prepared = asyncio.run(executor.prepare(call, context))
        if prepared is not None:
            return _outcome_payload(prepared)
        outcome = asyncio.run(executor.execute(call, context))
        return _outcome_payload(outcome)
    finally:
        db.close()


__all__ = ["create_pi_bridge_token", "router"]
