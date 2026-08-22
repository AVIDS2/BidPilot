"""Assistant API router for the governed server-side Harness."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.chat.service import resolve_conversation_project_context
from app.db import get_db
from app.providers.service import get_provider_config
from app.runtime.service import (
    assistant_turn_idempotency_key,
    find_idempotent_runtime_run,
)
from app.runtime.model import AgentModelConfigurationError, resolve_agent_model
from app.security.secrets import decrypt_secret
from app.usage.schemas import ProviderSource
from app.usage.service import (
    ASSISTANT_MESSAGE_STARTED,
    UsageLimitExceeded,
    check_assistant_quota,
    record_usage_event,
)

from .attachments import (
    MAX_ATTACHMENT_BYTES,
    extract_attachment_text,
    hydrate_assistant_attachments,
    stage_assistant_attachment,
)
from .schemas import AssistantAttachmentUploadResponse, AssistantRequest
from app.runtime.operator_adapter import stream_existing_assistant_run, stream_operator_assistant_response

router = APIRouter(prefix="/assistant", tags=["assistant"])
logger = logging.getLogger(__name__)

SSE_HEARTBEAT_SECONDS = max(5, int(os.getenv("DOCPILOT_ASSISTANT_SSE_HEARTBEAT_SECONDS", "12")))


async def _with_sse_heartbeats(
    stream: AsyncIterator[str],
    *,
    heartbeat_seconds: float | None = None,
) -> AsyncIterator[str]:
    """Keep an assistant SSE response alive while its upstream is quiet.

    The pending ``anext`` task is deliberately not cancelled on a heartbeat;
    cancelling it would also cancel the Harness/provider generator that owns
    the durable run. A comment frame is valid SSE and ignored by clients.
    """
    interval = heartbeat_seconds if heartbeat_seconds is not None else SSE_HEARTBEAT_SECONDS
    iterator = stream.__aiter__()
    pending: asyncio.Future[str] | None = None
    try:
        while True:
            if pending is None:
                pending = asyncio.ensure_future(iterator.__anext__())
            done, _ = await asyncio.wait({pending}, timeout=interval)
            if not done:
                yield ": keep-alive\n\n"
                continue
            try:
                event = pending.result()
            except StopAsyncIteration:
                return
            finally:
                pending = None
            yield event
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
            with suppress(asyncio.CancelledError):
                await pending
        close = getattr(iterator, "aclose", None)
        if close is not None:
            with suppress(RuntimeError):
                await close()


def _assistant_sse_response(stream: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        _with_sse_heartbeats(stream),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/attachments", response_model=AssistantAttachmentUploadResponse)
async def upload_assistant_attachment(
    kind: Literal["file", "image"] = "file",
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_auth),
) -> AssistantAttachmentUploadResponse:
    """Stage an attachment privately before an assistant turn or project ingestion."""
    data = await file.read()
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=413, detail="Attachment too large")
    extraction = extract_attachment_text(
        filename=file.filename or "untitled",
        content_type=file.content_type or "application/octet-stream",
        data=data,
        kind=kind,
    )
    staged = stage_assistant_attachment(
        db,
        current_user=user,
        filename=file.filename or "untitled",
        content_type=file.content_type or "application/octet-stream",
        data=data,
        kind=kind,
        extraction=extraction,
    )
    return staged.model_copy(update={"extracted_text": ""})


@router.post("/stream")
async def assistant_stream(
    payload: AssistantRequest,
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Stream one governed Harness turn via Server-Sent Events.

    The Harness owns conversational tool selection and durable execution
    records. Long-running bid pipelines remain separate LangGraph workflows
    linked from the resulting runtime run.

    SSE event types:
    - ``assistant.start``: agent begins processing
    - ``assistant.message``: incremental token from LLM (streamed)
    - ``assistant.tool_started``: a tool is being executed
    - ``assistant.tool_succeeded``: tool completed with result
    - ``assistant.tool_failed``: tool execution failed
    - ``assistant.missing_input``: a required business field is needed before execution
    - ``assistant.confirmation_requested``: a governed action needs approval
    - ``assistant.end``: agent finished
    """
    # A transport retry must replay before any mutable preflight work:
    # attachment hydration, provider lookup, quota accounting, or conversation
    # allocation. The same client request ID therefore has exactly one cost.
    if payload.confirmation is None:
        existing = find_idempotent_runtime_run(
            db,
            user,
            idempotency_key=assistant_turn_idempotency_key(
                user_id=user.id,
                client_request_id=payload.client_request_id,
            ),
        )
        if existing is not None:
            return _assistant_sse_response(stream_existing_assistant_run(db, existing))

    project_id = resolve_conversation_project_context(
        db,
        user,
        conversation_id=payload.conversation_id,
        requested_project_id=payload.project_id,
    )
    payload = payload.model_copy(
        update={
            "project_id": project_id,
            "attachments": hydrate_assistant_attachments(
                db,
                current_user=user,
                attachments=payload.attachments,
            ),
        }
    )

    provider_source, provider_type, provider_id, api_key, base_url, model, provider_config_id = _resolve_request_provider(db, user, payload)
    payload = payload.model_copy(update={"provider_config_id": provider_config_id})
    try:
        _record_assistant_usage(db, user, payload, provider_source)
    except UsageLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    return _assistant_sse_response(
        stream_operator_assistant_response(
            db,
            user,
            payload,
            provider_type=provider_type,
            provider_id=provider_id,
            provider_source=provider_source,
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
    )


def _resolve_request_provider(
    db: Session,
    user: CurrentUser,
    payload: AssistantRequest,
) -> tuple[ProviderSource, str, str | None, str | None, str | None, str | None, str | None]:
    if not payload.provider_config_id:
        try:
            resolved = resolve_agent_model()
        except AgentModelConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        return (
            ProviderSource.OFFICIAL,
            resolved.provider_type,
            resolved.provider_id,
            resolved.api_key,
            resolved.base_url,
            resolved.model,
            None,
        )

    config = get_provider_config(db, payload.provider_config_id, user.id)
    if config is None or not config.is_active:
        # An explicit provider_config_id selects a user-owned billing and
        # authorization boundary. Never silently replace a deleted BYOK choice
        # with a platform-funded model.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider config not found")

    try:
        resolved = resolve_agent_model(
            provider_type=config.provider_type,
            provider_id=config.provider_id,
            api_key=decrypt_secret(config.api_key),
            base_url=config.api_url,
            model=config.model,
        )
    except AgentModelConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return (
        ProviderSource.BYOK,
        resolved.provider_type,
        resolved.provider_id,
        resolved.api_key,
        resolved.base_url,
        resolved.model,
        config.id,
    )


def _record_assistant_usage(
    db: Session,
    user: CurrentUser,
    payload: AssistantRequest,
    provider_source: ProviderSource,
) -> None:
    if payload.confirmation is not None:
        return

    check_assistant_quota(db, user.id, user.org_id, provider_source)
    record_usage_event(
        db,
        user_id=user.id,
        org_id=user.org_id,
        project_id=payload.project_id,
        event_type=ASSISTANT_MESSAGE_STARTED,
        provider_source=provider_source,
        metadata_json={
            "conversation_id": payload.conversation_id,
            "reasoning_effort": payload.reasoning_effort,
            "attachment_count": len(payload.attachments),
        },
    )
    db.commit()
