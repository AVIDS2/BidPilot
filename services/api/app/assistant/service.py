"""Assistant harness service and SSE event orchestration."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.chat.service import create_conversation, get_conversation, get_conversation_messages, save_message
from app.models import ChatTaskState

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

    task_state = _get_task_state(db, conversation_id)
    if _is_pending_confirmation(task_state):
        if _is_cancel_followup(payload.message):
            async for event in _handle_confirmation(
                db,
                user,
                AssistantConfirmation(approved=False, tool_name=task_state.tool_name or "", arguments=task_state.arguments_json or {}),
                conversation_id,
            ):
                yield event
            _clear_task_state(db, conversation_id)
            return
        if _is_confirm_followup(payload.message):
            async for event in _handle_confirmation(
                db,
                user,
                AssistantConfirmation(approved=True, tool_name=task_state.tool_name or "", arguments=task_state.arguments_json or {}),
                conversation_id,
            ):
                yield event
            _clear_task_state(db, conversation_id)
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
        _clear_task_state(db, conversation_id)
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

    _clear_task_state(db, conversation_id)
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


def _resume_pending_intent(
    db: Session,
    conversation_id: str,
    message: str,
    task_state: ChatTaskState | None = None,
) -> AssistantIntent | None:
    if task_state is not None:
        if task_state.status != "needs_input" or task_state.tool_name != "create_project":
            return None
        missing_fields = task_state.missing_fields_json or {}
        if "name" not in (missing_fields.get("fields") or []):
            return None
    elif not _last_assistant_asked_for_project_name(db, conversation_id):
        return None

    text = message.strip()
    if _is_delegate_followup(text):
        name = _default_project_name()
    else:
        name = _extract_followup_project_name(text)
    if not name:
        return None

    return AssistantIntent(
        mode="tool_action",
        tool_name="create_project",
        arguments={**(task_state.arguments_json if task_state else {}), "name": name, "scenario_package": "bidpilot"},
    )


def _last_assistant_asked_for_project_name(db: Session, conversation_id: str) -> bool:
    conversation_messages = get_conversation_messages(db, conversation_id)
    if len(conversation_messages) < 2:
        return False

    last_assistant = next(
        (entry for entry in reversed(conversation_messages[:-1]) if entry.role == "assistant"),
        None,
    )
    if last_assistant is None:
        return False
    return "项目名称" in last_assistant.content or "项目名" in last_assistant.content


def _is_delegate_followup(text: str) -> bool:
    normalized = re.sub(r"[。！!?？\s]+", "", text)
    delegate_phrases = {
        "你来",
        "你定",
        "你决定",
        "随便",
        "都行",
        "默认",
        "开始吧",
        "继续",
        "可以",
        "行",
        "好",
    }
    return normalized in delegate_phrases or any(phrase in normalized for phrase in ("你来", "你定", "随便", "默认"))


def _extract_followup_project_name(text: str) -> str | None:
    stripped = text.strip().strip("。！!?？")
    if not stripped or stripped in {"项目", "创建一个新项目", "开始吧", "你来", "随便", "都行", "可以", "行"}:
        return None
    if len(stripped) > 80:
        stripped = stripped[:80]
    return stripped


def _default_project_name() -> str:
    return f"新建投标项目 {datetime.now(UTC).strftime('%m%d')}"


def _get_task_state(db: Session, conversation_id: str) -> ChatTaskState | None:
    return db.get(ChatTaskState, conversation_id)


def _set_task_state(
    db: Session,
    conversation_id: str,
    *,
    status: str,
    tool_name: str | None,
    arguments: dict,
    missing_fields: list[str],
) -> None:
    state = db.get(ChatTaskState, conversation_id)
    if state is None:
        state = ChatTaskState(conversation_id=conversation_id)
        db.add(state)
    state.status = status
    state.tool_name = tool_name
    state.arguments_json = dict(arguments)
    state.missing_fields_json = {"fields": list(missing_fields)}
    db.commit()


def _clear_task_state(db: Session, conversation_id: str) -> None:
    state = db.get(ChatTaskState, conversation_id)
    if state is None:
        return
    db.delete(state)
    db.commit()


def _is_pending_confirmation(task_state: ChatTaskState | None) -> bool:
    return task_state is not None and task_state.status == "needs_confirmation" and bool(task_state.tool_name)


def _is_confirm_followup(message: str) -> bool:
    normalized = re.sub(r"[。！!?？\s]+", "", message.strip())
    return normalized in {"确认", "同意", "可以", "行", "好", "开始", "开始吧", "执行", "继续", "确定"}


def _is_cancel_followup(message: str) -> bool:
    normalized = re.sub(r"[。！!?？\s]+", "", message.strip())
    return normalized in {"取消", "算了", "不要", "别", "停止", "先不", "不创建", "不用了"}
