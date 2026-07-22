"""Compatibility adapter from the deterministic assistant to runtime events.

This is intentionally a narrow migration seam: intent selection remains local,
but every effect, approval and terminal answer goes through the product-owned
runtime control plane.  The legacy assistant SSE shape is rendered from those
durable events so the web client can migrate independently.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.orm import Session

from app.assistant.audit import redact_text
from app.assistant.runtime import AssistantRuntime
from app.assistant.schemas import AssistantConfirmation, AssistantIntent, AssistantRequest
from app.auth.schemas import CurrentUser
from app.chat.service import create_conversation, get_conversation, save_message
from app.models import RuntimeAction, RuntimeApproval, RuntimeEvent, RuntimeRun
from contracts.runtime import RuntimeApprovalDecisionType, RuntimeEventType

from .events import latest_event_sequence, list_events_after
from .registry import is_workflow_capability
from .service import (
    RuntimeApprovalExpiredError,
    RuntimeApprovalResolvedError,
    cancel_runtime_run,
    complete_runtime_run,
    create_runtime_run,
    execute_capability,
    fail_runtime_run,
    find_pending_approval_for_conversation,
    resolve_approval,
)


_runtime = AssistantRuntime()


def runtime_v1_enabled() -> bool:
    """Keep rollout opt-in until deterministic and graph adapters have parity."""
    return os.getenv("DOCPILOT_ASSISTANT_RUNTIME_V1", "false").lower() == "true"


async def stream_runtime_assistant_response(
    db: Session,
    user: CurrentUser,
    payload: AssistantRequest,
    *,
    intent_override: AssistantIntent | None = None,
) -> AsyncGenerator[str, None]:
    """Handle one deterministic assistant turn through ``RuntimeRun`` records."""
    conversation_id = _ensure_conversation(db, user, payload)

    if payload.confirmation is not None and payload.confirmation.approval_id:
        save_message(db, conversation_id, "user", payload.message)
        async for event in _resume_approval(db, user, conversation_id, payload.confirmation):
            yield event
        return

    pending = find_pending_approval_for_conversation(db, user, conversation_id)
    if pending is not None and _is_confirmation_followup(payload.message):
        save_message(db, conversation_id, "user", payload.message)
        async for event in _resume_approval(
            db,
            user,
            conversation_id,
            AssistantConfirmation(
                approved=not _is_cancellation_followup(payload.message),
                tool_name=_approval_capability(db, pending),
                approval_id=pending.id,
            ),
        ):
            yield event
        return

    save_message(db, conversation_id, "user", payload.message)
    run = create_runtime_run(
        db,
        user,
        kind="assistant_turn",
        engine="deterministic",
        project_id=payload.project_id,
        conversation_id=conversation_id,
        provider_config_id=payload.provider_config_id,
        reasoning_effort=payload.reasoning_effort,
        approval_mode=payload.approval_mode,
        input_json={
            "message": payload.message,
            "attachment_names": [attachment.name for attachment in payload.attachments],
        },
    )
    yield _sse(
        "assistant.start",
        {
            "conversation_id": conversation_id,
            "runtime_run_id": run.id,
            "state": "thinking",
        },
    )

    try:
        intent = intent_override or _resume_followup_intent(db, conversation_id, payload.message)
        if intent is None:
            intent = await _runtime.classify(payload.message, payload.project_id)
        yield _sse("assistant.intent_detected", {"mode": intent.mode, "tool_name": intent.tool_name})

        if intent.mode == "needs_input":
            response = intent.response or "我还需要一些信息才能继续。"
            _save_pending_input_state(db, conversation_id, intent)
            yield _sse(
                "assistant.missing_input",
                {
                    "tool_name": intent.tool_name,
                    "missing_fields": intent.missing_fields,
                    "message": response,
                },
            )
            complete_runtime_run(db, run.id, response)
            save_message(db, conversation_id, "assistant", response)
            for event in _render_runtime_events(db, run.id, after_sequence=1, conversation_id=conversation_id):
                yield event
            return

        if intent.mode == "answer" or intent.tool_name is None:
            response = intent.response or "我可以继续帮你处理这个请求。"
            complete_runtime_run(db, run.id, response)
            save_message(db, conversation_id, "assistant", response)
            for event in _render_runtime_events(db, run.id, after_sequence=1, conversation_id=conversation_id):
                yield event
            return

        arguments = _enrich_intent_arguments(intent, payload)
        _clear_pending_input_state(db, conversation_id)
        execution = execute_capability(
            db,
            user,
            run_id=run.id,
            capability_name=intent.tool_name,
            arguments=arguments,
            action_key=f"deterministic:{intent.tool_name}:1",
        )
        if execution.approval is not None:
            for event in _render_runtime_events(db, run.id, after_sequence=1, conversation_id=conversation_id):
                yield event
            return

        response = execution.result.summary if execution.result is not None else "操作已完成。"
        complete_runtime_run(db, run.id, response)
        save_message(db, conversation_id, "assistant", response)
        for event in _render_runtime_events(db, run.id, after_sequence=1, conversation_id=conversation_id):
            yield event
    except Exception as exc:
        safe_error = redact_text(str(exc))
        try:
            fail_runtime_run(db, run.id, f"执行失败：{safe_error}", error_code="assistant_turn_failed")
        except ValueError:
            # A terminal approval expiry already has its own durable state.
            pass
        save_message(db, conversation_id, "assistant", f"执行失败：{safe_error}")
        for event in _render_runtime_events(db, run.id, after_sequence=1, conversation_id=conversation_id):
            yield event


async def _resume_approval(
    db: Session,
    user: CurrentUser,
    conversation_id: str,
    confirmation: AssistantConfirmation,
) -> AsyncGenerator[str, None]:
    approval = db.get(RuntimeApproval, confirmation.approval_id)
    if approval is None:
        yield _sse("assistant.tool_failed", {"tool_name": confirmation.tool_name, "error_message": "未找到待处理审批。", "state": "failed"})
        yield _sse("assistant.end", {"conversation_id": conversation_id, "state": "failed"})
        return
    action = db.get(RuntimeAction, approval.action_id)
    if action is None:
        yield _sse("assistant.tool_failed", {"tool_name": confirmation.tool_name, "error_message": "审批关联的操作不可用。", "state": "failed"})
        yield _sse("assistant.end", {"conversation_id": conversation_id, "state": "failed"})
        return
    run = db.get(RuntimeRun, action.run_id)
    if run is None or run.conversation_id != conversation_id:
        yield _sse("assistant.tool_failed", {"tool_name": confirmation.tool_name, "error_message": "审批不属于当前会话。", "state": "failed"})
        yield _sse("assistant.end", {"conversation_id": conversation_id, "state": "failed"})
        return

    before_sequence = latest_event_sequence(db, run.id)
    yield _sse(
        "assistant.start",
        {"conversation_id": conversation_id, "runtime_run_id": run.id, "state": "thinking"},
    )
    try:
        if not confirmation.approved:
            resolve_approval(
                db,
                user,
                approval_id=approval.id,
                decision=RuntimeApprovalDecisionType.REJECT,
            )
            message = "已取消这次操作。"
            cancel_runtime_run(db, run.id, message)
        else:
            execution = resolve_approval(
                db,
                user,
                approval_id=approval.id,
                decision=RuntimeApprovalDecisionType.APPROVE,
            )
            message = execution.result.summary if execution.result is not None else "操作已完成。"
            complete_runtime_run(db, run.id, message)
        save_message(db, conversation_id, "assistant", message)
        for event in _render_runtime_events(
            db,
            run.id,
            after_sequence=before_sequence,
            conversation_id=conversation_id,
        ):
            yield event
    except (RuntimeApprovalExpiredError, RuntimeApprovalResolvedError) as exc:
        safe_error = redact_text(str(exc))
        yield _sse(
            "assistant.tool_failed",
            {"tool_name": action.capability_name, "error_message": safe_error, "state": "failed"},
        )
        yield _sse("assistant.end", {"conversation_id": conversation_id, "runtime_run_id": run.id, "state": "failed"})
    except Exception as exc:
        safe_error = redact_text(str(exc))
        try:
            fail_runtime_run(db, run.id, f"执行失败：{safe_error}", error_code="approval_execution_failed")
        except ValueError:
            pass
        save_message(db, conversation_id, "assistant", f"执行失败：{safe_error}")
        for event in _render_runtime_events(
            db,
            run.id,
            after_sequence=before_sequence,
            conversation_id=conversation_id,
        ):
            yield event


def _render_runtime_events(
    db: Session,
    run_id: str,
    *,
    after_sequence: int,
    conversation_id: str,
) -> list[str]:
    rendered: list[str] = []
    for event in list_events_after(db, run_id, after_sequence=after_sequence):
        rendered.extend(_render_runtime_event(event, conversation_id))
    return rendered


def _render_runtime_event(event: RuntimeEvent, conversation_id: str) -> list[str]:
    payload = event.payload_json or {}
    capability = str(payload.get("capability") or "")
    runtime_metadata = {"runtime_run_id": event.run_id, "runtime_sequence": event.sequence}
    if event.event_type == RuntimeEventType.PLAN_PROPOSED.value:
        plan_mode = str(payload.get("mode") or "answer")
        assistant_mode = "tool_action" if plan_mode == "tool" else plan_mode
        events = [
            _sse(
                "assistant.intent_detected",
                {
                    **runtime_metadata,
                    "mode": assistant_mode,
                    "tool_name": capability or None,
                },
            )
        ]
        if plan_mode == "needs_input":
            missing_fields = [
                field
                for field in (payload.get("missing_fields") or [])
                if isinstance(field, str) and field
            ]
            events.append(
                _sse(
                    "assistant.missing_input",
                    {
                        **runtime_metadata,
                        "tool_name": capability or None,
                        "missing_fields": missing_fields,
                        "message": event.public_summary,
                        "state": "needs_input",
                    },
                )
            )
        return events
    if event.event_type == RuntimeEventType.CAPABILITY_STARTED.value:
        return [
            _sse(
                "assistant.tool_started",
                {**runtime_metadata, "tool_name": capability, "state": "executing_tool"},
            )
        ]
    if event.event_type == RuntimeEventType.CAPABILITY_SUCCEEDED.value:
        result = {key: value for key, value in payload.items() if key != "capability"}
        events: list[str] = []
        if is_workflow_capability(capability):
            events.append(
                _sse(
                    "assistant.workflow_started",
                    {**runtime_metadata, "tool_name": capability, "result": result, "state": "running_workflow"},
                )
            )
        events.append(
            _sse(
                "assistant.tool_succeeded",
                {
                    **runtime_metadata,
                    "tool_name": capability,
                    "result": result,
                    "summary": event.public_summary,
                    "state": "completed",
                },
            )
        )
        return events
    if event.event_type == RuntimeEventType.CAPABILITY_FAILED.value:
        return [
            _sse(
                "assistant.tool_failed",
                {
                    **runtime_metadata,
                    "tool_name": capability or "unknown",
                    "error_message": event.public_summary,
                    "state": "failed",
                },
            )
        ]
    if event.event_type == RuntimeEventType.APPROVAL_REQUESTED.value:
        confirmation = {
            **runtime_metadata,
            "approval_id": payload.get("approval_id"),
            "conversation_id": conversation_id,
            "tool_name": capability,
            "arguments": payload.get("arguments") or {},
            "message": payload.get("message") or "该操作需要你的确认。",
            "requires_typed_confirmation": bool(payload.get("requires_typed_confirmation")),
            "state": "needs_confirmation",
        }
        if isinstance(payload.get("expected_text"), str):
            confirmation["expected_text"] = payload["expected_text"]
        return [_sse("assistant.confirmation_requested", confirmation)]
    if event.event_type == RuntimeEventType.APPROVAL_RESOLVED.value:
        status = payload.get("status")
        if status in {"approved", "edited"}:
            return [
                _sse(
                    "assistant.tool_started",
                    {**runtime_metadata, "tool_name": capability, "state": "executing_tool"},
                )
            ]
        return []
    if event.event_type == RuntimeEventType.MESSAGE_COMPLETED.value:
        return [
            _sse(
                "assistant.message",
                {**runtime_metadata, "content": event.public_summary, "state": "completed"},
            )
        ]
    if event.event_type in {
        RuntimeEventType.RUN_COMPLETED.value,
        RuntimeEventType.RUN_CANCELLED.value,
        RuntimeEventType.RUN_FAILED.value,
    }:
        return [
            _sse(
                "assistant.end",
                {
                    **runtime_metadata,
                    "conversation_id": conversation_id,
                    "state": "failed" if event.event_type == RuntimeEventType.RUN_FAILED.value else "completed",
                },
            )
        ]
    return []


def _ensure_conversation(db: Session, user: CurrentUser, payload: AssistantRequest) -> str:
    if payload.conversation_id:
        conversation = get_conversation(db, payload.conversation_id, user.id)
        if conversation is not None:
            return conversation.id
    return create_conversation(db, user.id, payload.project_id).id


def _enrich_intent_arguments(intent: AssistantIntent, payload: AssistantRequest) -> dict[str, Any]:
    arguments = dict(intent.arguments)
    if payload.provider_config_id and intent.tool_name in {
        "start_draft_section",
        "start_redraft_section",
        "propose_memory_graph",
    }:
        arguments["provider_config_id"] = payload.provider_config_id
    if payload.reasoning_effort and intent.tool_name in {
        "start_draft_section",
        "start_redraft_section",
        "propose_memory_graph",
    }:
        arguments["reasoning_effort"] = payload.reasoning_effort
    return arguments


def _resume_followup_intent(
    db: Session,
    conversation_id: str,
    message: str,
) -> AssistantIntent | None:
    # Imported lazily to keep the old harness isolated while the migration flag is off.
    from app.assistant.service import _get_task_state, _resume_pending_intent

    return _resume_pending_intent(
        db,
        conversation_id,
        message,
        task_state=_get_task_state(db, conversation_id),
    )


def _save_pending_input_state(db: Session, conversation_id: str, intent: AssistantIntent) -> None:
    """Reuse the conversation task state for deterministic follow-up fields.

    Runtime V1 owns approvals through ``RuntimeApproval``. This small bridge is
    only for a missing input such as an explicitly selected knowledge record;
    it keeps both assistant entry points from diverging on multi-turn input.
    """
    from app.assistant.service import _set_task_state

    _set_task_state(
        db,
        conversation_id,
        status="needs_input",
        tool_name=intent.tool_name,
        arguments=intent.arguments,
        missing_fields=intent.missing_fields,
    )


def _clear_pending_input_state(db: Session, conversation_id: str) -> None:
    from app.assistant.service import _clear_task_state

    _clear_task_state(db, conversation_id)


def _approval_capability(db: Session, approval: RuntimeApproval) -> str:
    action = db.get(RuntimeAction, approval.action_id)
    return action.capability_name if action is not None else "unknown"


def _is_confirmation_followup(message: str) -> bool:
    normalized = re.sub(r"[。！!?？\s]+", "", message.strip())
    return normalized in {"确认", "同意", "可以", "行", "好", "开始", "开始吧", "执行", "继续", "确定", "取消", "算了", "不要", "别", "停止", "先不", "不用了"}


def _is_cancellation_followup(message: str) -> bool:
    normalized = re.sub(r"[。！!?？\s]+", "", message.strip())
    return normalized in {"取消", "算了", "不要", "别", "停止", "先不", "不用了"}


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
