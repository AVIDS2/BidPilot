"""Compatibility adapter from the deterministic assistant to runtime events.

This is intentionally a narrow migration seam: intent selection remains local,
but every effect, approval and terminal answer goes through the product-owned
runtime control plane.  The legacy assistant SSE shape is rendered from those
durable events so the web client can migrate independently.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.orm import Session

from app.assistant.runtime import AssistantRuntime
from app.assistant.schemas import AssistantConfirmation, AssistantIntent, AssistantRequest
from app.auth.schemas import CurrentUser
from app.chat.service import create_conversation, get_conversation, save_message
from app.models import RuntimeAction, RuntimeApproval, RuntimeEvent, RuntimeRun
from contracts.runtime import (
    RuntimeActionStatus,
    RuntimeApprovalDecisionType,
    RuntimeApprovalStatus,
    RuntimeEventType,
    RuntimeRunStatus,
)

from . import events as runtime_events
from .failures import classify_capability_failure
from .registry import get_capability_definition, is_workflow_capability
from .service import (
    RuntimeApprovalExpiredError,
    RuntimeApprovalResolvedError,
    assistant_turn_idempotency_key,
    cancel_runtime_run,
    complete_runtime_run,
    create_or_get_runtime_run,
    execute_capability,
    fail_runtime_run,
    find_idempotent_runtime_run,
    find_pending_approval_for_conversation,
    reconcile_runtime_run_for_replay,
    resolve_approval,
)


_runtime = AssistantRuntime()

_LEGACY_GENERATED_NARRATION = re.compile(
    r"^为推进当前任务，我先.+，再根据真实结果决定下一步。$"
)
_LEGACY_GENERATED_NARRATIONS = {
    "我已核对当前会话中的已知信息，正在整理可以直接回答的结论。",
    "当前项目范围还没有明确。我先查询可访问项目；若有同名项目，会用 short_id 请你确认目标。",
    "这个问题需要核对最新公开信息。我先检索相关来源，再根据结果组织可靠结论。",
    "目标范围已经确定。我先读取项目结构和现有资料，确认后续操作有足够依据。",
    "我先核对项目结构和现有资料，避免在信息不足时直接开始后续操作。",
    "起草前需要把目标章节和依据对齐。我会按已确认的范围推进，并将结果写入对应工作区。",
}


def _is_legacy_generated_narration(content: str) -> bool:
    """Hide only the retired template copy; keep natural historical trace text."""
    return content in _LEGACY_GENERATED_NARRATIONS or bool(
        _LEGACY_GENERATED_NARRATION.fullmatch(content)
    )


async def stream_runtime_assistant_response(
    db: Session,
    user: CurrentUser,
    payload: AssistantRequest,
    *,
    intent_override: AssistantIntent | None = None,
) -> AsyncGenerator[str, None]:
    """Handle one deterministic assistant turn through ``RuntimeRun`` records."""
    idempotency_key = assistant_turn_idempotency_key(
        user_id=user.id,
        client_request_id=payload.client_request_id,
    )
    if payload.confirmation is None:
        existing = find_idempotent_runtime_run(
            db,
            user,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            async for event in _replay_existing_run(
                db,
                existing,
                conversation_id=existing.conversation_id or payload.conversation_id or "",
            ):
                yield event
            return

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

    if pending is not None and _matches_typed_confirmation(pending, payload.message):
        save_message(db, conversation_id, "user", payload.message)
        payload_json = pending.payload_json if isinstance(pending.payload_json, dict) else {}
        pending_arguments = payload_json.get("arguments")
        confirmed_arguments = pending_arguments if isinstance(pending_arguments, dict) else {}
        async for event in _resume_approval(
            db,
            user,
            conversation_id,
            AssistantConfirmation(
                approved=True,
                tool_name=_approval_capability(db, pending),
                approval_id=pending.id,
                arguments={
                    **confirmed_arguments,
                    "confirmation_text": payload.message.strip(),
                },
            ),
        ):
            yield event
        return

    if pending is not None:
        save_message(db, conversation_id, "user", payload.message)
        reply = _pending_approval_status_reply(pending)
        save_message(db, conversation_id, "assistant", reply)
        payload_json = pending.payload_json if isinstance(pending.payload_json, dict) else {}
        yield _sse("assistant.start", {"conversation_id": conversation_id, "state": "needs_confirmation"})
        yield _sse("assistant.message", {"content": reply, "state": "needs_confirmation"})
        confirmation = {
            "approval_id": pending.id,
            "tool_name": _approval_capability(db, pending),
            "arguments": payload_json.get("arguments") or {},
            "message": payload_json.get("message") or reply,
            "requires_typed_confirmation": bool(payload_json.get("requires_typed_confirmation")),
            "state": "needs_confirmation",
        }
        if isinstance(payload_json.get("expected_text"), str):
            confirmation["expected_text"] = payload_json["expected_text"]
        yield _sse("assistant.confirmation_requested", confirmation)
        yield _sse("assistant.end", {"conversation_id": conversation_id, "state": "needs_confirmation"})
        return

    save_message(db, conversation_id, "user", payload.message, attachments=payload.attachments)
    creation = create_or_get_runtime_run(
        db,
        user,
        kind="assistant_turn",
        engine="deterministic",
        project_id=payload.project_id,
        conversation_id=conversation_id,
        provider_config_id=payload.provider_config_id,
        reasoning_effort=payload.reasoning_effort,
        approval_mode=payload.approval_mode,
        idempotency_key=idempotency_key,
        input_json={
            "message": payload.message,
            "client_request_id": payload.client_request_id,
            "attachment_names": [attachment.name for attachment in payload.attachments],
        },
    )
    if not creation.created:
        async for event in _replay_existing_run(
            db,
            creation.run,
            conversation_id=creation.run.conversation_id or conversation_id,
        ):
            yield event
        return

    run = creation.run
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
        failure = classify_capability_failure(exc)
        message = f"执行失败：{failure.message}"
        try:
            fail_runtime_run(db, run.id, message, error_code=failure.error_code)
        except ValueError:
            # A terminal approval expiry already has its own durable state.
            pass
        save_message(db, conversation_id, "assistant", message)
        for event in _render_runtime_events(db, run.id, after_sequence=1, conversation_id=conversation_id):
            yield event


async def _replay_existing_run(
    db: Session,
    run: RuntimeRun,
    *,
    conversation_id: str,
) -> AsyncGenerator[str, None]:
    """Render the durable trace instead of executing a retried deterministic turn."""
    run = reconcile_runtime_run_for_replay(db, run.id)
    state_by_status = {
        "awaiting_approval": "needs_confirmation",
        "failed": "failed",
        "expired": "failed",
        "cancelled": "completed",
        "succeeded": "completed",
    }
    state = state_by_status.get(run.status, "thinking")
    yield _sse(
        "assistant.start",
        {
            "conversation_id": conversation_id,
            "runtime_run_id": run.id,
            "state": state,
            "replayed": True,
        },
    )
    emitted_end = False
    for event in _render_runtime_events(
        db,
        run.id,
        after_sequence=0,
        conversation_id=conversation_id,
    ):
        if event.startswith("event: assistant.end"):
            emitted_end = True
        yield event
    if not emitted_end:
        yield _sse(
            "assistant.end",
            {
                "conversation_id": conversation_id,
                "runtime_run_id": run.id,
                "state": state,
                "replayed": True,
            },
        )


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

    before_sequence = runtime_events.latest_event_sequence(db, run.id)
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
            approval_payload = approval.payload_json if isinstance(approval.payload_json, dict) else {}
            requires_typed_confirmation = bool(approval_payload.get("requires_typed_confirmation"))
            if requires_typed_confirmation and "confirmation_text" in confirmation.arguments:
                stored_arguments = approval_payload.get("arguments")
                edited_arguments = {
                    **(stored_arguments if isinstance(stored_arguments, dict) else {}),
                    "confirmation_text": confirmation.arguments.get("confirmation_text"),
                }
                execution = resolve_approval(
                    db,
                    user,
                    approval_id=approval.id,
                    decision=RuntimeApprovalDecisionType.EDIT,
                    edited_arguments=edited_arguments,
                )
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
    except RuntimeApprovalExpiredError:
        safe_error = "审批已过期，未执行该操作。"
        error_code = "approval_expired"
        yield _sse(
            "assistant.tool_failed",
            {
                "tool_name": action.capability_name,
                "error_code": error_code,
                "error_message": safe_error,
                "state": "failed",
            },
        )
        yield _sse("assistant.end", {"conversation_id": conversation_id, "runtime_run_id": run.id, "state": "failed"})
    except RuntimeApprovalResolvedError:
        if (
            approval.status == RuntimeApprovalStatus.EXPIRED.value
            or action.status == RuntimeActionStatus.EXPIRED.value
            or run.status == RuntimeRunStatus.EXPIRED.value
        ):
            safe_error = "审批已过期，未执行该操作。"
            error_code = "approval_expired"
        else:
            safe_error = "该审批已经处理，无法重复执行。"
            error_code = "approval_already_resolved"
        yield _sse(
            "assistant.tool_failed",
            {
                "tool_name": action.capability_name,
                "error_code": error_code,
                "error_message": safe_error,
                "state": "failed",
            },
        )
        yield _sse("assistant.end", {"conversation_id": conversation_id, "runtime_run_id": run.id, "state": "failed"})
    except Exception as exc:
        failure = classify_capability_failure(exc)
        message = f"执行失败：{failure.message}"
        try:
            fail_runtime_run(db, run.id, message, error_code=failure.error_code)
        except ValueError:
            pass
        save_message(db, conversation_id, "assistant", message)
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
    for event in runtime_events.list_events_after(db, run_id, after_sequence=after_sequence):
        rendered.extend(_render_runtime_event(event, conversation_id))
    return rendered


def _render_runtime_event(event: RuntimeEvent, conversation_id: str) -> list[str]:
    payload = event.payload_json or {}
    capability = str(payload.get("capability") or "")
    action_id = payload.get("action_id") if isinstance(payload.get("action_id"), str) else None
    turn_id = payload.get("turn_id") if isinstance(payload.get("turn_id"), str) else None
    tool_call_id = payload.get("tool_call_id") if isinstance(payload.get("tool_call_id"), str) else action_id
    title = payload.get("title") if isinstance(payload.get("title"), str) else None
    runtime_metadata = {
        "runtime_run_id": event.run_id,
        "runtime_event_id": event.id,
        "runtime_parent_event_id": event.parent_event_id,
        "runtime_sequence": event.sequence,
        "runtime_timestamp": event.created_at.isoformat() if event.created_at else None,
    }
    if event.event_type in {
        RuntimeEventType.PLAN_PROPOSED.value,
        RuntimeEventType.PLAN_UPDATED.value,
    }:
        stage = payload.get("stage")
        if stage == "model_turn":
            return [
                _sse(
                    "assistant.turn_started",
                    {
                        **runtime_metadata,
                        "turn_id": turn_id,
                        "step": payload.get("step"),
                        "state": "thinking",
                        "phase": payload.get("phase"),
                        "completed_capabilities": payload.get("completed_capabilities") or [],
                    },
                )
            ]
        if stage == "turn_finished":
            return [
                _sse(
                    "assistant.turn_finished",
                    {
                        **runtime_metadata,
                        "turn_id": turn_id,
                        "summary": event.public_summary,
                        "state": "thinking",
                    },
                )
            ]
        if stage == "task_started":
            return [
                _sse(
                    "assistant.task_started",
                    {
                        **runtime_metadata,
                        "turn_id": turn_id,
                        "title": payload.get("title") or event.public_summary,
                        "summary": event.public_summary,
                        "skill_name": payload.get("skill_name"),
                        "state": "thinking",
                    },
                )
            ]
        if stage == "tool_plan":
            return [
                _sse(
                    "assistant.plan_updated",
                    {
                        **runtime_metadata,
                        "turn_id": turn_id,
                        "summary": event.public_summary,
                        "items": payload.get("items") or [],
                        "state": "thinking",
                    },
                )
            ]
        plan_mode = str(payload.get("mode") or "answer")
        assistant_mode = "tool_action" if plan_mode == "tool" else plan_mode
        plan_events = [
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
            plan_events.append(
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
        return plan_events
    if event.event_type == RuntimeEventType.CAPABILITY_STARTED.value:
        try:
            resolved_title = title or (get_capability_definition(capability).label_zh if capability else capability)
        except Exception:
            resolved_title = title or capability
        return [
            _sse(
                "assistant.tool_started",
                {
                    **runtime_metadata,
                    "tool_name": capability,
                    "tool_call_id": tool_call_id,
                    "turn_id": turn_id,
                    "title": resolved_title,
                    "arguments": payload.get("arguments") or {},
                    "state": "executing_tool",
                },
            )
        ]
    if event.event_type == RuntimeEventType.CAPABILITY_SUCCEEDED.value:
        result = {
            key: value
            for key, value in payload.items()
            if key not in {"capability", "action_id", "turn_id", "tool_call_id", "title"}
        }
        completion_events: list[str] = []
        if is_workflow_capability(capability):
            completion_events.append(
                _sse(
                    "assistant.workflow_started",
                    {
                        **runtime_metadata,
                        "tool_name": capability,
                        "tool_call_id": tool_call_id,
                        "turn_id": turn_id,
                        "title": title,
                        "result": result,
                        "state": "running_workflow",
                    },
                )
            )
        completion_events.append(
            _sse(
                "assistant.tool_succeeded",
                {
                    **runtime_metadata,
                    "tool_name": capability,
                    "tool_call_id": tool_call_id,
                    "turn_id": turn_id,
                    "title": title,
                    "result": result,
                    "summary": event.public_summary,
                    "state": "completed",
                },
            )
        )
        return completion_events
    if event.event_type == RuntimeEventType.CAPABILITY_FAILED.value:
        return [
            _sse(
                "assistant.tool_failed",
                {
                    **runtime_metadata,
                    "tool_name": capability or "unknown",
                    "tool_call_id": tool_call_id,
                    "turn_id": turn_id,
                    "title": title,
                    "error_code": payload.get("reason_code") or payload.get("error_code"),
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
            "tool_call_id": tool_call_id,
            "turn_id": turn_id,
            "title": title,
            "arguments": payload.get("arguments") or {},
            "message": payload.get("message") or "该操作需要你的确认。",
            "requires_typed_confirmation": bool(payload.get("requires_typed_confirmation")),
            "state": "needs_confirmation",
        }
        if isinstance(payload.get("expected_text"), str):
            confirmation["expected_text"] = payload["expected_text"]
        # Awaiting approval is a durable pause, so the stream boundary must be
        # replayable too. Rendering the end here avoids a second, ephemeral
        # assistant.end emitted by the live Harness coroutine.
        return [
            _sse("assistant.confirmation_requested", confirmation),
            _sse(
                "assistant.end",
                {
                    **runtime_metadata,
                    "conversation_id": conversation_id,
                    "state": "needs_confirmation",
                },
            ),
        ]
    if event.event_type == RuntimeEventType.APPROVAL_RESOLVED.value:
        status = payload.get("status")
        if status in {"approved", "edited"}:
            return [
                _sse(
                    "assistant.tool_started",
                    {
                        **runtime_metadata,
                        "tool_name": capability,
                        "tool_call_id": tool_call_id,
                        "turn_id": turn_id,
                        "title": title,
                        "state": "executing_tool",
                    },
                )
            ]
        return []
    if event.event_type == RuntimeEventType.REASONING_DELTA.value:
        # Raw provider thought is never a product-facing SSE payload. Only the
        # Harness-filtered public narration may enter the visible trace.
        if payload.get("source") != "harness":
            return []
        if _is_legacy_generated_narration(event.public_summary):
            return []
        return [
            _sse(
                "assistant.reasoning",
                {
                    **runtime_metadata,
                    "turn_id": turn_id,
                    "content": event.public_summary,
                    "title": payload.get("title") or event.public_summary,
                    "source": payload.get("source") or "provider",
                    "chunk_index": payload.get("chunk_index"),
                    "state": "streaming",
                },
            )
        ]
    if event.event_type == RuntimeEventType.REASONING_COMPLETED.value:
        if payload.get("source") != "harness":
            return []
        return [
            _sse(
                "assistant.reasoning_completed",
                {
                    **runtime_metadata,
                    "turn_id": turn_id,
                    "source": payload.get("source") or "provider",
                    "state": "completed",
                },
            )
        ]
    if event.event_type in {
        RuntimeEventType.MESSAGE_DELTA.value,
        RuntimeEventType.MESSAGE_COMPLETED.value,
    }:
        if event.event_type == RuntimeEventType.MESSAGE_COMPLETED.value and payload.get("delta_emitted"):
            return []
        return [
            _sse(
                "assistant.message",
                {
                    **runtime_metadata,
                    "turn_id": turn_id,
                    "content": event.public_summary,
                    "state": "thinking" if event.event_type == RuntimeEventType.MESSAGE_DELTA.value else "completed",
                },
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
                    "state": payload.get("state")
                    or ("failed" if event.event_type == RuntimeEventType.RUN_FAILED.value else "completed"),
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
    return normalized in {
        "确认",
        "同意",
        "可以",
        "行",
        "好",
        "好的",
        "开始",
        "开始吧",
        "执行",
        "继续",
        "确定",
        "确认执行",
        "确认删除",
        "删除",
        "删掉",
        "取消",
        "算了",
        "不要",
        "别",
        "停止",
        "先不",
        "不用了",
    }


def _is_cancellation_followup(message: str) -> bool:
    normalized = re.sub(r"[。！!?？\s]+", "", message.strip())
    return normalized in {"取消", "算了", "不要", "别", "停止", "先不", "不用了", "先别删", "不要删"}


def _pending_expected_text(approval: RuntimeApproval) -> str | None:
    payload = approval.payload_json if isinstance(approval.payload_json, dict) else {}
    expected = payload.get("expected_text")
    if isinstance(expected, str) and expected.strip():
        return expected.strip()
    return None


def _matches_typed_confirmation(approval: RuntimeApproval, message: str) -> bool:
    expected = _pending_expected_text(approval)
    if not expected:
        return False
    return message.strip() == expected


def _pending_approval_status_reply(approval: RuntimeApproval) -> str:
    payload = approval.payload_json if isinstance(approval.payload_json, dict) else {}
    capability = str(payload.get("capability") or "操作")
    message = str(payload.get("message") or "该操作仍在等待你的确认。")
    expected = _pending_expected_text(approval)
    if capability == "delete_project":
        base = "还没有删除。删除操作仍在等待你的确认，不会自动执行。"
        if expected:
            return f"{base}请在确认框输入完整项目名称「{expected}」并点确认，或回复「取消」。"
        return f"{base}请在确认框点确认，或回复「取消」。"
    return f"上一步操作仍在等待确认，尚未执行。\n\n{message}"


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
