"""Execute one queued assistant run independently of browser connections."""

from __future__ import annotations

from datetime import UTC, datetime
from sqlalchemy.orm import Session

from app.assistant.attachments import (
    attachment_planner_context,
    build_attachment_context,
    hydrate_assistant_attachments,
)
from app.assistant.schemas import AssistantAttachmentPayload, AssistantRequest
from app.assistant.task_state import pending_input_context
from app.auth.schemas import CurrentUser
from app.models import RuntimeRun, User
from app.providers.service import get_provider_config
from app.security.secrets import decrypt_secret

from .conversation import (
    load_authorized_memory,
    load_conversation_context,
    load_mem0_profile_context,
    memory_context_records,
)
from .model import resolve_agent_model
from .pi_adapter import stream_pi_assistant_response
from .service import cancel_runtime_run, fail_runtime_run


def _current_user(row: User) -> CurrentUser:
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


def _request_from_run(run: RuntimeRun) -> AssistantRequest:
    source = run.input_json if isinstance(run.input_json, dict) else {}
    names = source.get("attachment_names") if isinstance(source.get("attachment_names"), list) else []
    ids = source.get("attachment_ids") if isinstance(source.get("attachment_ids"), list) else []
    attachments = [
        AssistantAttachmentPayload(
            id=str(attachment_id),
            name=str(names[index]) if index < len(names) else "附件",
        )
        for index, attachment_id in enumerate(ids)
        if isinstance(attachment_id, str) and attachment_id
    ]
    policy = run.policy_snapshot_json if isinstance(run.policy_snapshot_json, dict) else {}
    approval_mode = str(policy.get("approval_mode") or "risky_only")
    if approval_mode not in {"request_approval", "risky_only", "full_access", "custom"}:
        approval_mode = "risky_only"
    return AssistantRequest(
        message=str(source.get("message") or ""),
        client_request_id=source.get("client_request_id") if isinstance(source.get("client_request_id"), str) else None,
        project_id=run.project_id,
        conversation_id=run.conversation_id,
        provider_config_id=run.provider_config_id,
        reasoning_effort=run.reasoning_effort if run.reasoning_effort in {"low", "medium", "high", "extra", "max"} else None,
        approval_mode=approval_mode,  # type: ignore[arg-type]
        attachments=attachments,
    )


async def execute_queued_assistant_run(db: Session, run: RuntimeRun) -> str:
    """Run Pi to a durable terminal state; no browser or SSE is required."""

    if run.status in {"succeeded", "failed", "cancelled", "expired"}:
        return run.status
    if run.status == "cancel_requested":
        cancel_runtime_run(db, run.id)
        return "cancelled"
    user_row = db.get(User, run.user_id)
    if user_row is None:
        fail_runtime_run(db, run.id, "助手所属用户不存在。", error_code="assistant_user_missing")
        return "failed"
    if not run.conversation_id:
        fail_runtime_run(db, run.id, "助手运行缺少会话上下文。", error_code="assistant_conversation_missing")
        return "failed"

    user = _current_user(user_row)
    payload = _request_from_run(run)
    source = run.input_json if isinstance(run.input_json, dict) else {}
    user_message_id = source.get("user_message_id") if isinstance(source.get("user_message_id"), str) else None
    payload = payload.model_copy(
        update={
            "attachments": hydrate_assistant_attachments(
                db,
                current_user=user,
                attachments=payload.attachments,
            )
        }
    )
    if not payload.message.strip():
        fail_runtime_run(db, run.id, "助手运行缺少用户消息。", error_code="assistant_message_missing")
        return "failed"

    if run.provider_config_id:
        config = get_provider_config(db, run.provider_config_id, user.id)
        if config is None or not config.is_active:
            fail_runtime_run(db, run.id, "所选模型配置已不可用。", error_code="provider_config_missing")
            return "failed"
        resolved = resolve_agent_model(
            provider_type=config.provider_type,
            provider_id=config.provider_id,
            api_key=decrypt_secret(config.api_key),
            base_url=config.api_url,
            model=run.model or config.model,
        )
    else:
        resolved = resolve_agent_model()

    run.status = "running"
    run.started_at = run.started_at or datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    conversation_window = load_conversation_context(
        db,
        run.conversation_id,
        exclude_message_id=user_message_id,
    )
    pending_input = pending_input_context(db, run.conversation_id)
    memory_context = load_authorized_memory(
        db,
        user,
        project_id=run.project_id,
        query=payload.message,
    )
    profile_context = await load_mem0_profile_context(
        user_id=user.id,
        org_id=user.org_id,
        query=payload.message,
    )
    async for _event in stream_pi_assistant_response(
        db,
        user,
        run=run,
        conversation_id=run.conversation_id,
        provider_type=resolved.provider_type,
        provider_id=resolved.provider_id,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        model=resolved.model,
        user_message=payload.message,
        conversation_window=conversation_window,
        memory_context_records=memory_context_records(memory_context) + profile_context,
        memory_context_version=memory_context.memory_version if memory_context is not None else None,
        available_attachments=attachment_planner_context(payload.attachments),
        attachment_context=build_attachment_context("", payload.attachments),
        active_project_id=run.project_id,
        pending_input=pending_input,
        approval_mode=payload.approval_mode,
        reasoning_effort=payload.reasoning_effort,
    ):
        # RuntimeEvent/chat persistence and the Redis live projection all happen
        # inside the Pi adapter. The worker does not own the browser socket.
        continue
    db.refresh(run)
    return run.status


__all__ = ["execute_queued_assistant_run"]
