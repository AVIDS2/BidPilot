"""Assistant harness service and SSE event orchestration."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.runtime.policy import get_tool_policy
from app.auth.schemas import CurrentUser
from app.chat.service import (
    create_conversation,
    get_conversation,
    resolve_conversation_project_context,
    save_message,
)
from app.models import ChatTaskState
from app.runtime.failures import classify_capability_failure

from .guardrails import requires_confirmation
from .audit import (
    begin_confirmed_action,
    cancel_pending_action,
    record_action_failed,
    record_action_started,
    record_action_succeeded,
    record_pending_approval,
    redact_arguments,
    redact_text,
)
from .runtime import AssistantRuntime
from .schemas import AssistantConfirmation, AssistantIntent, AssistantRequest, AssistantToolResult
from .task_state import (
    clear_task_state,
    get_task_state,
    is_task_state_stale,
    set_task_state,
)
from .tools import execute_tool


runtime = AssistantRuntime()


async def stream_assistant_response(
    db: Session,
    user: CurrentUser,
    payload: AssistantRequest,
) -> AsyncGenerator[str, None]:
    project_id = resolve_conversation_project_context(
        db,
        user,
        conversation_id=payload.conversation_id,
        requested_project_id=payload.project_id,
    )
    payload = payload.model_copy(update={"project_id": project_id})
    conversation_id = _ensure_conversation(db, user, payload)
    if payload.confirmation is None:
        save_message(db, conversation_id, "user", payload.message, attachments=payload.attachments)

    yield _sse("assistant.start", {"conversation_id": conversation_id, "state": "thinking"})

    if payload.confirmation is not None:
        async for event in _handle_confirmation(db, user, payload.confirmation, conversation_id):
            yield event
        return

    task_state = _get_task_state(db, conversation_id)
    if _is_stale_task_state(task_state):
        _clear_task_state(db, conversation_id)
        task_state = None
    if _is_pending_confirmation(task_state):
        message = "上一步操作仍在等待确认，尚未执行。请使用页面中的确认或取消控件。"
        save_message(db, conversation_id, "assistant", message)
        yield _sse("assistant.message", {"content": message, "state": "needs_confirmation"})
        yield _sse(
            "assistant.end",
            {"conversation_id": conversation_id, "state": "needs_confirmation"},
        )
        return

    intent = _resume_pending_intent(db, conversation_id, payload.message, task_state)
    if intent is None:
        intent = await runtime.classify(payload.message, payload.project_id)
    yield _sse(
        "assistant.intent_detected",
        {"mode": intent.mode, "tool_name": intent.tool_name},
    )

    if intent.mode == "needs_input":
        response = intent.response or "我还需要一些信息才能继续。"
        yield _sse(
            "assistant.missing_input",
            {
                "tool_name": intent.tool_name,
                "missing_fields": intent.missing_fields,
                "message": response,
            },
        )
        _set_task_state(
            db,
            conversation_id,
            status="needs_input",
            tool_name=intent.tool_name,
            arguments=intent.arguments,
            missing_fields=intent.missing_fields,
        )
        yield _message_and_end(db, conversation_id, response)
        return

    if intent.mode == "answer" or intent.tool_name is None:
        _clear_task_state(db, conversation_id)
        response = intent.response or "我可以继续帮你处理这个请求。"
        yield _message_and_end(db, conversation_id, response)
        return

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

    if requires_confirmation(intent.tool_name, payload.approval_mode):
        response = _confirmation_message(intent.tool_name, arguments)
        confirmation_payload = _confirmation_payload(intent.tool_name, arguments, response)
        approval = record_pending_approval(
            db,
            user,
            conversation_id=conversation_id,
            tool_name=intent.tool_name,
            arguments=arguments,
            approval_mode=payload.approval_mode,
            payload=confirmation_payload,
        )
        confirmation_payload["approval_id"] = approval.id
        confirmation_payload["conversation_id"] = conversation_id
        yield _sse(
            "assistant.confirmation_requested",
            confirmation_payload,
        )
        _set_task_state(
            db,
            conversation_id,
            status="needs_confirmation",
            tool_name=intent.tool_name,
            arguments=arguments,
            missing_fields=[],
        )
        yield _message_and_end(db, conversation_id, response)
        return

    audit = record_action_started(
        db,
        user,
        conversation_id=conversation_id,
        tool_name=intent.tool_name,
        arguments=arguments,
        approval_mode=payload.approval_mode,
    )
    try:
        result = execute_tool(db, user, intent.tool_name, arguments)
    except Exception as exc:
        failure = classify_capability_failure(exc)
        record_action_failed(db, audit, failure.message)
        yield _tool_failed(intent.tool_name, failure.message)
        yield _message_and_end(db, conversation_id, f"执行失败：{failure.message}")
        return

    record_action_succeeded(db, audit, result.summary)
    async for event in _emit_tool_result(db, conversation_id, result, arguments):
        yield event


async def _handle_confirmation(
    db: Session,
    user: CurrentUser,
    confirmation: AssistantConfirmation,
    conversation_id: str,
) -> AsyncGenerator[str, None]:
    if not confirmation.approved:
        message = "已取消这次操作。"
        cancel_pending_action(
            db,
            user,
            conversation_id=conversation_id,
            tool_name=confirmation.tool_name,
            approval_id=confirmation.approval_id,
        )
        save_message(db, conversation_id, "assistant", message)
        _clear_task_state(db, conversation_id)
        yield _sse(
            "assistant.message",
            {"content": message, "state": "completed"},
        )
        return

    try:
        audit = begin_confirmed_action(
            db,
            user,
            conversation_id=conversation_id,
            tool_name=confirmation.tool_name,
            arguments=confirmation.arguments,
            approval_id=confirmation.approval_id,
        )
    except Exception as exc:
        failure = classify_capability_failure(exc)
        yield _tool_failed(confirmation.tool_name, failure.message)
        yield _message_and_end(db, conversation_id, f"执行失败：{failure.message}")
        return
    yield _sse(
        "assistant.tool_started",
        {
            "tool_name": confirmation.tool_name,
            "arguments": confirmation.arguments,
            "state": "executing_tool",
        },
    )
    try:
        result = execute_tool(db, user, confirmation.tool_name, confirmation.arguments)
    except Exception as exc:
        failure = classify_capability_failure(exc)
        record_action_failed(db, audit, failure.message)
        yield _tool_failed(confirmation.tool_name, failure.message)
        return

    record_action_succeeded(db, audit, result.summary)
    _clear_task_state(db, conversation_id)
    async for event in _emit_tool_result(db, conversation_id, result, confirmation.arguments):
        yield event


async def _emit_tool_result(
    db: Session,
    conversation_id: str | None,
    result: AssistantToolResult,
    arguments: dict,
) -> AsyncGenerator[str, None]:
    summary = redact_text(result.summary)
    transport_result = redact_arguments(result.result)
    if result.workflow:
        yield _sse(
            "assistant.workflow_started",
            {
                "tool_name": result.tool_name,
                "arguments": arguments,
                "result": transport_result,
                "state": "running_workflow",
            },
        )

    terminal_state = "running_workflow" if result.workflow else "completed"
    yield _sse(
        "assistant.tool_succeeded",
        {
            "tool_name": result.tool_name,
            "result": transport_result,
            "summary": summary,
            "state": terminal_state,
        },
    )
    yield _sse("assistant.message", {"content": summary, "state": terminal_state})
    if conversation_id:
        save_message(db, conversation_id, "assistant", summary)
    yield _sse(
        "assistant.end",
        {
            "full_response": summary,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


def _ensure_conversation(db: Session, user: CurrentUser, payload: AssistantRequest) -> str:
    if payload.conversation_id:
        conversation = get_conversation(db, payload.conversation_id, user.id)
        if conversation is not None:
            return conversation.id
    return create_conversation(db, user.id, payload.project_id).id


def _confirmation_message(tool_name: str, arguments: dict) -> str:
    if tool_name == "create_demo_workspace":
        return "需要你确认：我将创建内置演示工作区。它会占用一个项目名额，但不会使用 AI 额度。"
    if tool_name == "create_project":
        return f"需要你确认：我将创建项目「{arguments.get('name')}」。"
    if tool_name == "start_draft_section":
        return f"需要你确认：我将启动章节「{arguments.get('section_key')}」的起草工作流。"
    if tool_name == "start_redraft_section":
        return f"需要你确认：我将启动章节「{arguments.get('section_key')}」的重写工作流。"
    if tool_name == "propose_memory_graph":
        return "需要你确认：我将从这条已验证的项目知识生成实体关系提案。该操作会使用一次模型额度，结果仍需人工审核。"
    if tool_name == "attach_uploaded_documents":
        return f"需要你确认：我将把 {len(arguments.get('attachment_ids') or [])} 个附件加入项目资料包并开始解析。"
    if tool_name == "generate_readiness_pack":
        return "需要你确认：我将生成当前项目的投标准备度包。"
    if tool_name == "delete_project":
        return "需要你确认：这是删除项目操作。请输入完整项目名称后我再执行删除。"
    return "需要你确认后我再执行这个操作。"


def _confirmation_payload(tool_name: str, arguments: dict, message: str) -> dict:
    policy = get_tool_policy(tool_name)
    payload = {
        "tool_name": tool_name,
        "arguments": arguments,
        "message": message,
        "state": "needs_confirmation",
        "requires_typed_confirmation": bool(policy and policy.requires_typed_confirmation),
    }
    expected_text = arguments.get("project_name") or arguments.get("name")
    if policy and policy.requires_typed_confirmation and expected_text:
        payload["expected_text"] = str(expected_text)
    return payload


def _tool_failed(tool_name: str, error_message: str) -> str:
    safe_error = redact_text(error_message)
    return _sse(
        "assistant.tool_failed",
        {
            "tool_name": tool_name,
            "error_message": safe_error,
            "state": "failed",
        },
    )


def _message_and_end(db: Session, conversation_id: str, content: str) -> str:
    save_message(db, conversation_id, "assistant", content)
    return (
        _sse("assistant.message", {"content": content, "state": "completed"})
        + _sse(
            "assistant.end",
            {
                "conversation_id": conversation_id,
                "full_response": content,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _resume_pending_intent(
    db: Session,
    conversation_id: str,
    message: str,
    task_state: ChatTaskState | None = None,
) -> AssistantIntent | None:
    if task_state is not None:
        if task_state.status == "needs_input" and task_state.tool_name == "propose_memory_graph":
            missing_fields = task_state.missing_fields_json or {}
            if "memory_record_id" not in (missing_fields.get("fields") or []):
                return None
            memory_record_id = _extract_uuid(message)
            if not memory_record_id:
                return AssistantIntent(
                    mode="needs_input",
                    tool_name="propose_memory_graph",
                    arguments=task_state.arguments_json or {},
                    missing_fields=["memory_record_id"],
                    response="我还需要有效的共享知识记录 ID，才能安全生成实体关系提案。",
                )
            return AssistantIntent(
                mode="workflow_trigger",
                tool_name="propose_memory_graph",
                arguments={**(task_state.arguments_json or {}), "memory_record_id": memory_record_id},
            )
        if task_state.status == "needs_input" and task_state.tool_name == "submit_review_decision":
            arguments = dict(task_state.arguments_json or {})
            missing_fields = task_state.missing_fields_json or {}
            required = list(missing_fields.get("fields") or [])
            candidate_id = _extract_uuid(message)
            if not candidate_id:
                return AssistantIntent(
                    mode="needs_input",
                    tool_name="submit_review_decision",
                    arguments=arguments,
                    missing_fields=required,
                    response="请提供待审核章节或候选版本的完整 ID。",
                )
            if "section_id" in required:
                arguments["section_id"] = candidate_id
                required.remove("section_id")
                required.append("section_version_id")
            elif "section_version_id" in required:
                arguments["section_version_id"] = candidate_id
                required.remove("section_version_id")
            if required:
                return AssistantIntent(
                    mode="needs_input",
                    tool_name="submit_review_decision",
                    arguments=arguments,
                    missing_fields=required,
                    response="请继续提供待审核候选版本的完整 ID。",
                )
            return AssistantIntent(
                mode="tool_action",
                tool_name="submit_review_decision",
                arguments=arguments,
            )
        if task_state.status != "needs_input" or task_state.tool_name != "create_project":
            return None
        missing_fields = task_state.missing_fields_json or {}
        if "name" not in (missing_fields.get("fields") or []):
            return None
    else:
        return None

    name = _extract_followup_project_name(message)
    if not name:
        return None

    return AssistantIntent(
        mode="tool_action",
        tool_name="create_project",
        arguments={**(task_state.arguments_json if task_state else {}), "name": name, "scenario_package": "bidpilot"},
    )


def _extract_followup_project_name(text: str) -> str | None:
    stripped = text.strip().strip("。！!?？")
    if not stripped:
        return None
    if len(stripped) > 80:
        stripped = stripped[:80]
    return stripped


def _extract_uuid(text: str) -> str | None:
    match = re.search(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        text,
    )
    return match.group(0) if match else None


def _get_task_state(db: Session, conversation_id: str) -> ChatTaskState | None:
    return get_task_state(db, conversation_id)


def _set_task_state(
    db: Session,
    conversation_id: str,
    *,
    status: str,
    tool_name: str | None,
    arguments: dict,
    missing_fields: list[str],
) -> None:
    set_task_state(
        db,
        conversation_id,
        status=status,
        tool_name=tool_name,
        arguments=arguments,
        missing_fields=missing_fields,
    )


def _clear_task_state(db: Session, conversation_id: str) -> None:
    clear_task_state(db, conversation_id)


def _is_pending_confirmation(task_state: ChatTaskState | None) -> bool:
    return task_state is not None and task_state.status == "needs_confirmation" and bool(task_state.tool_name)


def _is_stale_task_state(task_state: ChatTaskState | None) -> bool:
    return is_task_state_stale(task_state)
