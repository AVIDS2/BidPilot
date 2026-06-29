"""Assistant API router — powered by LangGraph ReAct agent."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.chat.service import create_conversation, get_conversation, save_message
from app.db import get_db

from .attachments import (
    MAX_ATTACHMENT_BYTES,
    build_attachment_context,
    extract_attachment_text,
    remember_attachment_text,
)
from .schemas import AssistantAttachmentUploadResponse, AssistantRequest
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
    # Resolve or create conversation
    conversation_id = _ensure_conversation(db, user, payload)
    save_message(db, conversation_id, "user", payload.message)

    # Resolve user's BYOK provider if specified
    api_key, base_url, model = None, None, None
    if payload.provider_config_id:
        from app.chat.service import _resolve_provider_config
        from app.security.secrets import decrypt_secret
        config = _resolve_provider_config(db, user.id, payload.provider_config_id)
        if config:
            api_key = decrypt_secret(config.api_key)
            base_url = config.api_url
            model = config.model

    # Build agent with fresh db session and user context
    agent = build_agent(db, user, api_key=api_key, base_url=base_url, model=model)

    config = {"configurable": {"thread_id": conversation_id}}
    agent_message = build_attachment_context(payload.message, payload.attachments)
    messages = [HumanMessage(content=agent_message)]

    async def generate():
        full_response = ""
        async for sse_chunk in stream_agent_events(agent, messages, config, conversation_id):
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


def _ensure_conversation(db: Session, user: CurrentUser, payload: AssistantRequest) -> str:
    if payload.conversation_id:
        conversation = get_conversation(db, payload.conversation_id, user.id)
        if conversation is not None:
            return conversation.id
    return create_conversation(db, user.id, payload.project_id).id
