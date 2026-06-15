"""Assistant harness service and SSE event orchestration."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.chat.service import create_conversation, get_conversation, save_message

from .guardrails import requires_confirmation
from .runtime import AssistantRuntime
from .schemas import AssistantConfirmation, AssistantIntent, AssistantRequest, AssistantToolResult
from .tools import execute_tool


runtime = AssistantRuntime()


async def stream_assistant_response(
    db: Session,
    user: CurrentUser,
    payload: AssistantRequest,
) -> AsyncGenerator[str, None]:
    conversation_id = _ensure_conversation(db, user, payload)
    save_message(db, conversation_id, "user", payload.message)

    yield _sse("assistant.start", {"conversation_id": conversation_id, "state": "thinking"})

    if payload.confirmation is not None:
        async for event in _handle_confirmation(db, user, payload.confirmation, conversation_id):
            yield event
        return

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
        yield _message_and_end(db, conversation_id, response)
        return

    if intent.mode == "answer" or intent.tool_name is None:
        response = intent.response or "我可以继续帮你处理这个请求。"
        yield _message_and_end(db, conversation_id, response)
        return

    arguments = dict(intent.arguments)
    if payload.provider_config_id and intent.tool_name in {"start_draft_section", "start_redraft_section"}:
        arguments["provider_config_id"] = payload.provider_config_id

    if requires_confirmation(intent.tool_name):
        response = _confirmation_message(intent.tool_name, arguments)
        yield _sse(
            "assistant.confirmation_requested",
            {
                "tool_name": intent.tool_name,
                "arguments": arguments,
                "message": response,
            },
        )
        yield _message_and_end(db, conversation_id, response)
        return

    try:
        result = execute_tool(db, user, intent.tool_name, arguments)
    except Exception as exc:
        yield _tool_failed(intent.tool_name, str(exc))
        yield _message_and_end(db, conversation_id, f"执行失败：{exc}")
        return

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
        save_message(db, conversation_id, "assistant", message)
        yield _sse(
            "assistant.message",
            {"content": message, "state": "completed"},
        )
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
        yield _tool_failed(confirmation.tool_name, str(exc))
        return

    async for event in _emit_tool_result(db, conversation_id, result, confirmation.arguments):
        yield event


async def _emit_tool_result(
    db: Session,
    conversation_id: str | None,
    result: AssistantToolResult,
    arguments: dict,
) -> AsyncGenerator[str, None]:
    if result.workflow:
        yield _sse(
            "assistant.workflow_started",
            {
                "tool_name": result.tool_name,
                "arguments": arguments,
                "result": result.result,
                "state": "running_workflow",
            },
        )

    yield _sse(
        "assistant.tool_succeeded",
        {
            "tool_name": result.tool_name,
            "result": result.result,
            "summary": result.summary,
            "state": "completed",
        },
    )
    yield _sse("assistant.message", {"content": result.summary, "state": "completed"})
    if conversation_id:
        save_message(db, conversation_id, "assistant", result.summary)
    yield _sse(
        "assistant.end",
        {
            "full_response": result.summary,
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
    if tool_name == "create_project":
        return f"需要你确认：我将创建项目「{arguments.get('name')}」。"
    if tool_name == "start_draft_section":
        return f"需要你确认：我将启动章节「{arguments.get('section_key')}」的起草工作流。"
    if tool_name == "start_redraft_section":
        return f"需要你确认：我将启动章节「{arguments.get('section_key')}」的重写工作流。"
    return "需要你确认后我再执行这个操作。"


def _tool_failed(tool_name: str, error_message: str) -> str:
    return _sse(
        "assistant.tool_failed",
        {
            "tool_name": tool_name,
            "error_message": error_message,
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
