"""Internal tool bridge for the Pi sidecar.

The sidecar is deliberately not given database credentials or a user session.
Every tool call returns through this endpoint, where the existing BidPilot
policy, approval, idempotency and audit boundaries remain authoritative.
"""

from __future__ import annotations

import os
from hashlib import sha256
from typing import Any

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .model import AgentModelConfigurationError, resolve_agent_model
from app.assistant.task_state import pending_input_context
from app.auth.schemas import CurrentUser
from app.db import SessionLocal
from app.memory.service import memory_context_for_agent
from app.models import Notification, RuntimeRun, User
from app.providers.service import get_provider_config
from app.security.secrets import decrypt_secret
from contracts.pi_bridge import encode_pi_bridge_token
from contracts.runtime import RuntimeEventType
from .bidpilot_harness_adapter import BidPilotToolExecutor
from .events import RuntimeEventDraft, publish_event
from .harness_core import HarnessExecutionContext, HarnessToolCall
from .registry import CAPABILITY_REGISTRY
from .subagent_control import create_subagent_runs
from .tool_catalog import _TOOL_PARAMETER_SCHEMAS
from .service import create_or_get_runtime_run


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


class PiSystemWake(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wake_run_id: str = Field(min_length=1, max_length=64)


def _secret() -> str:
    # In production the deployment must provide a dedicated secret. Falling
    # back to the JWT secret keeps local compose/dev usable without creating a
    # second credential, while never placing a secret in source or responses.
    value = os.getenv("DOCPILOT_PI_INTERNAL_SECRET") or os.getenv("DOCPILOT_JWT_SECRET")
    if not value:
        raise RuntimeError("DOCPILOT_PI_INTERNAL_SECRET is not configured")
    return value


def create_pi_bridge_token(*, run: RuntimeRun, user: CurrentUser) -> str:
    return encode_pi_bridge_token(
        run_id=run.id,
        user_id=user.id,
        org_id=user.org_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        plan=user.plan,
        org_slug=user.org_slug,
        secret=_secret(),
        ttl_seconds=_TOKEN_TTL_SECONDS,
    )


def _decode_token(authorization: str | None, *, purpose: str = "pi-tool-bridge") -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Pi bridge authorization required")
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
    except (jwt.PyJWTError, RuntimeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid Pi bridge authorization") from exc
    if claims.get("purpose") != purpose:
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
        if payload.name == "spawn_subagents":
            try:
                result = create_subagent_runs(
                    db,
                    user,
                    parent_run_id=run.id,
                    arguments=payload.arguments,
                )
            except ValueError as exc:
                code = str(exc) or "subagent_input_invalid"
                return {
                    "kind": "failed",
                    "publicSummary": "子 Agent 派生参数无效或超过治理限制。",
                    "modelPayload": {"error_code": code, "retryable": False},
                    "publicPayload": {"error_code": code},
                    "errorCode": code,
                    "recoverable": False,
                }
            publish_event(
                db,
                run.id,
                RuntimeEventDraft(
                    type=RuntimeEventType.CAPABILITY_PROGRESSED,
                    public_summary=f"已派生 {len(result['children'])} 个子 Agent。",
                    payload={
                        "capability": "subagent",
                        "phase": "children_spawned",
                        "tool_call_id": payload.tool_call_id,
                        "turn_id": context.turn_id,
                        "children": [
                            {
                                "run_id": child["run_id"],
                                "profile": child.get("profile"),
                                "mode": child.get("mode"),
                                "status": child.get("status"),
                            }
                            for child in result["children"]
                        ],
                    },
                ),
            )
            # A Pi tool call must not hold the model stream open while durable
            # workers run. Return child identities immediately; terminal
            # observations re-enter the parent through the signed system-wake
            # path instead of a fabricated user message.
            public_summary = f"已派生 {len(result['children'])} 个受治理子 Agent，后台运行中。"
            return {
                "kind": "succeeded",
                "publicSummary": public_summary,
                "modelPayload": result,
                "publicPayload": {
                    "mode": result["mode"],
                    "status": result.get("status"),
                    "children": [
                        {"run_id": child["run_id"], "status": child.get("status")}
                        for child in result["children"]
                    ],
                },
                "recoverable": True,
            }
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


@router.post("/runs/{run_id}/execute")
async def execute_queued_pi_run(
    run_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Run one queued assistant turn from Worker, independent of the browser."""

    claims = _decode_token(authorization, purpose="assistant-task")
    if claims.get("run_id") != run_id:
        raise HTTPException(status_code=403, detail="Assistant task run scope mismatch")
    db: Session = SessionLocal()
    try:
        run = db.get(RuntimeRun, run_id)
        if run is None or run.user_id != claims.get("user_id") or run.org_id != claims.get("org_id"):
            raise HTTPException(status_code=404, detail="Assistant runtime run not found")
        if run.kind != "assistant_turn" or run.engine != "pi":
            raise HTTPException(status_code=409, detail="Runtime run is not a queued Pi assistant turn")
        if run.status in {"succeeded", "failed", "cancelled", "expired"}:
            return {"status": run.status, "run_id": run.id}
        if run.status == "running":
            # A duplicate broker delivery must not start a second model loop.
            raise HTTPException(status_code=409, detail="Assistant runtime run is already executing")
        from .assistant_execution import execute_queued_assistant_run

        status = await execute_queued_assistant_run(db, run)
        return {"status": status, "run_id": run.id}
    finally:
        db.close()


def _runtime_user(db: Session, row: User) -> CurrentUser:
    return CurrentUser(
        id=row.id,
        email=row.email,
        display_name=row.display_name,
        role=row.role,
        plan=row.subscription.plan if row.subscription is not None else "starter",
        email_verified=row.email_verified,
        disabled=row.disabled,
        org_id=row.org_id,
        org_slug=row.organization.slug if row.organization is not None else "",
    )


def _wake_conversation_id(db: Session, source: RuntimeRun) -> str | None:
    if source.kind == "subagent" and source.parent_run_id:
        parent = db.get(RuntimeRun, source.parent_run_id)
        return parent.conversation_id if parent is not None else None
    return source.conversation_id


def _has_pending_wake(db: Session, *, user_id: str, conversation_id: str, wake_run_id: str) -> bool:
    from .background_tasks import _runtime_run_id_from_wake_link

    notifications = db.scalars(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.type == "agent_task",
            Notification.read.is_(False),
        )
    )
    return any(
        _runtime_run_id_from_wake_link(item.link, conversation_id) == wake_run_id
        for item in notifications
    )


@router.post("/wakes/resume")
async def resume_pi_from_system_wake(
    payload: PiSystemWake,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Resume a conversation from durable runtime state without a user message."""
    claims = _decode_token(authorization, purpose="agent-system-wake")
    if claims.get("wake_run_id") != payload.wake_run_id:
        raise HTTPException(status_code=403, detail="Agent wake scope mismatch")

    db: Session = SessionLocal()
    try:
        source = db.get(RuntimeRun, payload.wake_run_id)
        if source is None or source.kind not in {"subagent", "workflow_bridge", "deep_research"}:
            raise HTTPException(status_code=404, detail="Wake runtime not found")
        if source.status not in {"succeeded", "failed", "cancelled", "expired"}:
            raise HTTPException(status_code=409, detail="Wake runtime is not terminal")
        conversation_id = _wake_conversation_id(db, source)
        if not conversation_id:
            return {"status": "ignored", "reason": "conversation_missing"}

        key_material = f"agent-system-wake:{source.user_id}:{source.id}".encode("utf-8")
        idempotency_key = f"assistant-wake:{sha256(key_material).hexdigest()}"
        user_row = db.get(User, source.user_id)
        if user_row is None:
            raise HTTPException(status_code=404, detail="Wake user not found")
        user = _runtime_user(db, user_row)
        if not _has_pending_wake(
            db,
            user_id=user.id,
            conversation_id=conversation_id,
            wake_run_id=source.id,
        ):
            return {"status": "ignored", "reason": "wake_already_consumed"}

        config = get_provider_config(db, source.provider_config_id, user.id) if source.provider_config_id else None
        try:
            resolved = (
                resolve_agent_model(
                    provider_type=config.provider_type,
                    provider_id=config.provider_id,
                    api_key=decrypt_secret(config.api_key),
                    base_url=config.api_url,
                    model=source.model or config.model,
                )
                if config is not None
                else resolve_agent_model()
            )
        except AgentModelConfigurationError as exc:
            raise HTTPException(status_code=503, detail="Agent model is unavailable") from exc

        creation = create_or_get_runtime_run(
            db,
            user,
            kind="assistant_turn",
            engine="pi",
            project_id=source.project_id,
            conversation_id=conversation_id,
            provider_config_id=source.provider_config_id,
            model=source.model,
            reasoning_effort=source.reasoning_effort,
            approval_mode=str((source.policy_snapshot_json or {}).get("approval_mode") or "risky_only"),
            idempotency_key=idempotency_key,
            input_json={"system_wake_run_id": source.id, "source_kind": source.kind},
        )
        run = creation.run
        if not creation.created:
            return {"status": run.status, "runtime_run_id": run.id, "duplicate": True}

        summary = str((source.result_json or {}).get("summary") or source.error_message or "")[:2000]
        try:
            memory = memory_context_for_agent(
                db,
                current_user=user,
                project_id=source.project_id,
                query=summary or "后台任务状态更新",
                top_k=4,
            )
        except Exception:
            memory = None
        from .conversation import load_conversation_context, load_mem0_profile_context, memory_context_records

        memory_records = memory_context_records(memory)
        profile_records = await load_mem0_profile_context(
            user_id=user.id,
            org_id=user.org_id,
            query=summary or "后台任务状态更新",
        )

        # Keep the internal bridge import direction one-way. The public Pi
        # adapter already imports this module to mint capability tokens, so
        # importing it at module load time here would form a cycle.
        from .pi_adapter import stream_pi_assistant_response

        async for _event in stream_pi_assistant_response(
            db,
            user,
            run=run,
            conversation_id=conversation_id,
            provider_type=resolved.provider_type,
            provider_id=resolved.provider_id,
            api_key=resolved.api_key,
            base_url=resolved.base_url,
            model=resolved.model,
            user_message="",
            conversation_window=load_conversation_context(db, conversation_id),
            memory_context_records=memory_records + profile_records,
            memory_context_version=memory.memory_version if memory is not None else None,
            available_attachments=[],
            attachment_context="",
            active_project_id=source.project_id,
            pending_input=pending_input_context(db, conversation_id),
            approval_mode=str((source.policy_snapshot_json or {}).get("approval_mode") or "risky_only"),
            reasoning_effort=source.reasoning_effort,
            wake_runtime_run_id=source.id,
            system_wake=True,
        ):
            pass
        db.refresh(run)
        return {"status": run.status, "runtime_run_id": run.id, "duplicate": False}
    finally:
        db.close()


__all__ = ["create_pi_bridge_token", "router"]
