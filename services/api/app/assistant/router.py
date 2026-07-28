"""Assistant API router for the governed server-side Harness."""

from __future__ import annotations

import logging
import os
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agent.llm import AgentModelConfigurationError, resolve_agent_model
from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.chat.service import resolve_conversation_project_context
from app.db import get_db
from app.models import RuntimeAction, RuntimeRun
from app.providers.service import get_provider_config
from app.runtime.service import (
    assistant_turn_idempotency_key,
    find_idempotent_runtime_run,
    find_pending_approval_for_conversation,
)
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
from .runtime import classify_locally
from .schemas import AssistantAttachmentUploadResponse, AssistantIntent, AssistantRequest
from .service import stream_assistant_response
from app.runtime.assistant_adapter import (
    _is_confirmation_followup,
    runtime_v1_enabled,
    stream_runtime_assistant_response,
)
from app.runtime.operator_adapter import stream_existing_assistant_run, stream_operator_assistant_response

router = APIRouter(prefix="/assistant", tags=["assistant"])
logger = logging.getLogger(__name__)

# These names are accepted only so an already deployed environment can move to
# the canonical value without splitting the public assistant behavior.
LEGACY_ASSISTANT_ENGINE_ALIASES = {
    "operator": "harness",
    "streaming_harness": "harness",
}
LEGACY_ASSISTANT_ENGINE_ALIAS_RETIREMENT_DATE = "2026-09-30"


def _assistant_engine() -> str:
    """Return the one supported production assistant runtime.

    ``operator`` and ``streaming_harness`` remain accepted environment aliases
    during migration, but both resolve to the same governed Harness path.
    """
    configured = os.getenv("DOCPILOT_ASSISTANT_ENGINE", "harness").lower()
    return LEGACY_ASSISTANT_ENGINE_ALIASES.get(configured, configured)


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
            return StreamingResponse(
                stream_existing_assistant_run(db, existing),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

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
    if assistant_engine == "harness":
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
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Unsupported assistant runtime: {assistant_engine}",
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
