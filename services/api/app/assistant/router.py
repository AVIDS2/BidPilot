"""Assistant API router — powered by LangGraph ReAct agent."""

from __future__ import annotations

import os
import logging
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.chat.service import (
    create_conversation,
    get_conversation,
    resolve_conversation_project_context,
    save_message,
)
from app.db import get_db
from app.memory.service import memory_context_for_agent
from app.models import RuntimeAction, RuntimeRun
from app.providers.service import get_provider_config
from app.runtime.service import find_pending_approval_for_conversation
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
    hydrate_assistant_attachments,
    stage_assistant_attachment,
)
from .runtime import classify_locally
from .schemas import AssistantAttachmentUploadResponse, AssistantIntent, AssistantRequest
from .service import stream_assistant_response
from app.runtime.assistant_adapter import (
    _is_confirmation_followup,
    runtime_v1_enabled,
    stream_runtime_assistant_response,
)
from app.runtime.operator_adapter import stream_operator_assistant_response
from ..agent.graph import build_agent
from ..agent.streaming import stream_agent_events

router = APIRouter(prefix="/assistant", tags=["assistant"])
logger = logging.getLogger(__name__)


def _assistant_engine() -> str:
    """Use the governed operator runtime unless local development opts out."""
    return os.getenv("DOCPILOT_ASSISTANT_ENGINE", "operator").lower()


def _deterministic_demo_intent(payload: AssistantRequest) -> AssistantIntent | None:
    """Recognize only the no-model first-run demo capability.

    All other messages remain with the configured assistant engine. This keeps
    the fast path bounded instead of turning the local classifier into a
    general replacement for the LangGraph operator.
    """
    if payload.confirmation is not None:
        return None
    intent = classify_locally(payload.message, payload.project_id)
    return intent if intent.tool_name == "create_demo_workspace" else None


def _resumes_deterministic_runtime_approval(
    db: Session,
    user: CurrentUser,
    payload: AssistantRequest,
) -> bool:
    """Keep a demo approval on its original durable Runtime run.

    The operator adapter owns only ``langgraph_operator`` runs, so routing a
    confirmation for a deterministic run back to it would strand the approval.
    """
    if not payload.conversation_id or (
        payload.confirmation is None and not _is_confirmation_followup(payload.message)
    ):
        return False
    approval = find_pending_approval_for_conversation(db, user, payload.conversation_id)
    if approval is None:
        return False
    action = db.get(RuntimeAction, approval.action_id)
    run = db.get(RuntimeRun, action.run_id) if action is not None else None
    return run is not None and run.engine == "deterministic"


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

    # A first-run demo seeds bounded built-in data through Runtime; it must not
    # depend on a provider configuration, model availability, or AI quota.
    deterministic_demo_intent = _deterministic_demo_intent(payload)
    if deterministic_demo_intent is not None:
        payload = payload.model_copy(update={"provider_config_id": None})
    if deterministic_demo_intent is not None or _resumes_deterministic_runtime_approval(
        db,
        user,
        payload,
    ):
        return StreamingResponse(
            stream_runtime_assistant_response(
                db,
                user,
                payload,
                intent_override=deterministic_demo_intent,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    provider_source, provider_type, provider_id, api_key, base_url, model, provider_config_id = _resolve_request_provider(db, user, payload)
    payload = payload.model_copy(update={"provider_config_id": provider_config_id})
    try:
        _record_assistant_usage(db, user, payload, provider_source)
    except UsageLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    assistant_engine = _assistant_engine()
    if assistant_engine == "operator":
        return StreamingResponse(
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
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    if assistant_engine == "deterministic":
        return StreamingResponse(
            (
                stream_runtime_assistant_response(db, user, payload)
                if runtime_v1_enabled()
                else stream_assistant_response(db, user, payload)
            ),
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

    memory_context = _load_agent_memory_context(db, user, payload)

    # Build agent with fresh db session and user context
    agent = build_agent(
        db,
        user,
        provider_type=provider_type,
        provider_id=provider_id,
        api_key=api_key,
        base_url=base_url,
        model=model,
        provider_config_id=payload.provider_config_id,
        reasoning_effort=payload.reasoning_effort,
        approval_mode=payload.approval_mode,
        memory_context=memory_context,
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
) -> tuple[ProviderSource, str, str | None, str | None, str | None, str | None, str | None]:
    if not payload.provider_config_id:
        return ProviderSource.OFFICIAL, "openai", None, None, None, None, None

    config = get_provider_config(db, payload.provider_config_id, user.id)
    if config is None or not config.is_active:
        # An explicit provider_config_id selects a user-owned billing and
        # authorization boundary. Never silently replace a deleted BYOK choice
        # with a platform-funded model.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider config not found")

    return (
        ProviderSource.BYOK,
        config.provider_type,
        config.provider_id,
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


def _load_agent_memory_context(db: Session, user: CurrentUser, payload: AssistantRequest):
    """Memory retrieval is additive: a degraded memory path cannot stop an Agent run."""
    try:
        return memory_context_for_agent(
            db,
            current_user=user,
            project_id=payload.project_id,
            query=payload.message,
        )
    except Exception as exc:
        logger.warning("Assistant memory context unavailable: %s", type(exc).__name__)
        return None
