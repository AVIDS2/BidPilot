"""Assistant API router — powered by LangGraph ReAct agent."""

from __future__ import annotations

import os
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.chat.service import _resolve_provider_config, create_conversation, get_conversation, save_message
from app.db import get_db
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
    build_attachment_context,
    extract_attachment_text,
    remember_attachment_text,
)
from .schemas import AssistantAttachmentUploadResponse, AssistantRequest
from .service import stream_assistant_response
from ..agent.graph import build_agent
from ..agent.streaming import stream_agent_events

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/attachments", response_model=AssistantAttachmentUploadResponse)
async def upload_assistant_attachment(
    kind: Literal["file", "image"] = "file",
    file: UploadFile = File(...),
    user: CurrentUser = Depends(require_auth),  # noqa: ARG001 - auth gates chat-scoped uploads
) -> AssistantAttachmentUploadResponse:
    """Extract text from a chat-scoped attachment before an assistant turn."""
    data = await file.read()
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=413, detail="Attachment too large")
    extraction = extract_attachment_text(
        filename=file.filename or "untitled",
        content_type=file.content_type or "application/octet-stream",
        data=data,
        kind=kind,
    )
    remember_attachment_text(extraction)
    return extraction.model_copy(update={"extracted_text": ""})


@router.post("/stream")
async def assistant_stream(
    payload: AssistantRequest,
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Stream an AI assistant response via Server-Sent Events.

    Uses a LangGraph ReAct agent with platform tools. The agent
    autonomously decides which tools to call based on the user's
    natural language input.

    SSE event types:
    - ``assistant.start``: agent begins processing
    - ``assistant.message``: incremental token from LLM (streamed)
    - ``assistant.tool_started``: a tool is being executed
    - ``assistant.tool_succeeded``: tool completed with result
    - ``assistant.tool_failed``: tool execution failed
    - ``assistant.end``: agent finished
    """
    provider_source, provider_type, api_key, base_url, model, provider_config_id = _resolve_request_provider(db, user, payload)
    payload = payload.model_copy(update={"provider_config_id": provider_config_id})
    try:
        _record_assistant_usage(db, user, payload, provider_source)
    except UsageLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    if os.getenv("DOCPILOT_ASSISTANT_ENGINE", "langgraph").lower() == "deterministic":
        return StreamingResponse(
            stream_assistant_response(db, user, payload),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    if payload.confirmation is not None:
        return StreamingResponse(
            stream_assistant_response(db, user, payload),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Resolve or create conversation
    conversation_id = _ensure_conversation(db, user, payload)
    save_message(db, conversation_id, "user", payload.message)

    # Build agent with fresh db session and user context
    agent = build_agent(
        db,
        user,
        provider_type=provider_type,
        api_key=api_key,
        base_url=base_url,
        model=model,
        provider_config_id=payload.provider_config_id,
        reasoning_effort=payload.reasoning_effort,
        approval_mode=payload.approval_mode,
    )

    config = {"configurable": {"thread_id": conversation_id}}
    agent_message = build_attachment_context(payload.message, payload.attachments)
    messages = [HumanMessage(content=agent_message)]

    async def generate():
        full_response = ""
        async for sse_chunk in stream_agent_events(
            agent,
            messages,
            config,
            conversation_id,
            db=db,
            user=user,
            approval_mode=payload.approval_mode,
        ):
            # Capture the final message content for persistence
            if "assistant.message" in sse_chunk:
                import json
                try:
                    data_start = sse_chunk.index("data: ") + 6
                    data = json.loads(sse_chunk[data_start:].strip())
                    full_response += data.get("content", "")
                except (ValueError, json.JSONDecodeError):
                    pass
            yield sse_chunk

        # Save assistant response for conversation history
        if full_response:
            save_message(db, conversation_id, "assistant", full_response)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _resolve_request_provider(
    db: Session,
    user: CurrentUser,
    payload: AssistantRequest,
) -> tuple[ProviderSource, str, str | None, str | None, str | None, str | None]:
    if not payload.provider_config_id:
        return ProviderSource.OFFICIAL, "openai", None, None, None, None

    config = _resolve_provider_config(db, user.id, payload.provider_config_id)
    if config is None:
        return ProviderSource.OFFICIAL, "openai", None, None, None, None

    return (
        ProviderSource.BYOK,
        config.provider_type,
        decrypt_secret(config.api_key),
        config.api_url,
        config.model,
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


def _ensure_conversation(db: Session, user: CurrentUser, payload: AssistantRequest) -> str:
    if payload.conversation_id:
        conversation = get_conversation(db, payload.conversation_id, user.id)
        if conversation is not None:
            return conversation.id
    return create_conversation(db, user.id, payload.project_id).id
