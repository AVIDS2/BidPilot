"""Translate LangGraph astream_events to SSE events for the frontend."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from sqlalchemy.orm import Session

from app.assistant.audit import (
    record_action_failed,
    record_action_needs_approval,
    record_action_started,
    record_action_succeeded,
    redact_arguments,
    redact_text,
    validate_approval_mode,
)
from app.auth.schemas import CurrentUser
from app.models import AssistantActionAudit


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_agent_events(
    agent,
    messages: list,
    config: dict,
    conversation_id: str,
    db: Session | None = None,
    user: CurrentUser | None = None,
    approval_mode: str = "risky_only",
) -> AsyncGenerator[str, None]:
    """Stream agent execution as SSE events compatible with the frontend.

    Event mapping:
    - on_chat_model_stream → assistant.message (incremental token)
    - on_tool_start → assistant.tool_started
    - on_tool_end → assistant.tool_succeeded / assistant.tool_failed
    - end → assistant.end
    """
    yield _sse("assistant.start", {"conversation_id": conversation_id, "state": "thinking"})

    # Track token buffer for incremental message updates
    current_tool_name = None
    current_audit: AssistantActionAudit | None = None
    active_audits: dict[str, AssistantActionAudit] = {}
    awaiting_confirmation = False

    try:
        async for event in agent.astream_events(
            {"messages": messages},
            config=config,
            version="v2",
        ):
            kind = event.get("event", "")

            # Token-level streaming from the LLM
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk", {})
                content = getattr(chunk, "content", "") or ""
                if content:
                    yield _sse("assistant.message", {"content": content, "state": "thinking"})

            # LLM finished generating — check if it called a tool
            elif kind == "on_chat_model_end":
                output = event.get("data", {}).get("output", {})
                tool_calls = getattr(output, "tool_calls", []) or []
                if tool_calls:
                    for tc in tool_calls:
                        tool_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                        tool_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                        current_tool_name = tool_name
                        yield _sse("assistant.tool_started", {
                            "tool_name": tool_name,
                            "arguments": tool_args if isinstance(tool_args, dict) else {},
                            "state": "executing_tool",
                        })

            # Tool execution started
            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                if tool_name:
                    current_tool_name = tool_name
                    audit = _record_tool_start(
                        db,
                        user,
                        conversation_id,
                        tool_name,
                        _tool_input(event),
                        approval_mode,
                    )
                    if audit is not None:
                        current_audit = audit
                        active_audits[str(event.get("run_id") or tool_name)] = audit

            # Tool execution completed
            elif kind == "on_tool_end":
                tool_name = event.get("name", "") or current_tool_name
                audit = active_audits.pop(str(event.get("run_id") or tool_name), current_audit)
                output = event.get("data", {}).get("output", "")

                # Parse tool output
                result = {}
                summary = ""
                if isinstance(output, str):
                    try:
                        result = json.loads(output)
                        if "error" in result:
                            result = {**result, "error": redact_text(str(result["error"]))}
                        summary = _extract_summary(tool_name, result)
                    except (json.JSONDecodeError, TypeError):
                        summary = redact_text(output[:200])
                else:
                    summary = redact_text(str(output)[:200]) if output else ""
                summary = redact_text(summary)

                confirmation_payload = _extract_confirmation_request(tool_name, result)
                if confirmation_payload is not None:
                    awaiting_confirmation = True
                    if audit is not None and db is not None and user is not None:
                        approval = record_action_needs_approval(
                            db,
                            user,
                            audit,
                            payload=confirmation_payload,
                        )
                        confirmation_payload["approval_id"] = approval.id
                        confirmation_payload["conversation_id"] = conversation_id
                    yield _sse("assistant.confirmation_requested", confirmation_payload)
                    current_tool_name = None
                    current_audit = None
                    continue

                if audit is not None and db is not None:
                    if "error" in result:
                        record_action_failed(db, audit, str(result["error"]))
                    else:
                        record_action_succeeded(db, audit, summary)
                transport_result = redact_arguments(result)
                yield _sse("assistant.tool_succeeded", {
                    "tool_name": tool_name,
                    "result": transport_result,
                    "summary": summary,
                    "state": "completed",
                })
                current_tool_name = None
                current_audit = None

    except Exception as exc:
        safe_error = redact_text(str(exc))
        if current_audit is not None and db is not None:
            record_action_failed(db, current_audit, safe_error)
        yield _sse("assistant.tool_failed", {
            "tool_name": current_tool_name or "unknown",
            "error_message": safe_error,
            "state": "failed",
        })

    yield _sse("assistant.end", {
        "conversation_id": conversation_id,
        "state": "needs_confirmation" if awaiting_confirmation else "completed",
    })


def _record_tool_start(
    db: Session | None,
    user: CurrentUser | None,
    conversation_id: str,
    tool_name: str,
    arguments: dict,
    approval_mode: str,
) -> AssistantActionAudit | None:
    if db is None or user is None:
        return None
    return record_action_started(
        db,
        user,
        conversation_id=conversation_id,
        tool_name=tool_name,
        arguments=arguments,
        approval_mode=validate_approval_mode(approval_mode),
    )


def _tool_input(event: dict) -> dict:
    value = event.get("data", {}).get("input", {})
    return value if isinstance(value, dict) else {}


def _extract_confirmation_request(tool_name: str, result: dict) -> dict | None:
    """Translate guarded tool output into the product confirmation event."""
    if not result.get("requires_confirmation"):
        return None
    arguments = result.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}
    payload = {
        "tool_name": str(result.get("tool_name") or tool_name),
        "arguments": arguments,
        "message": str(result.get("message") or "需要你确认后我再执行这个操作。"),
        "state": "needs_confirmation",
        "requires_typed_confirmation": bool(result.get("requires_typed_confirmation")),
    }
    if "expected_text" in result:
        payload["expected_text"] = str(result["expected_text"])
    return payload


def _extract_summary(tool_name: str, result: dict) -> str:
    """Generate a human-readable summary from tool result."""
    if "error" in result:
        return f"操作失败：{result['error']}"
    if "count" in result:
        entity = tool_name.replace("list_", "").replace("search_", "")
        return f"找到 {result['count']} 条{entity}记录。"
    if "name" in result and "status" in result:
        return f"项目「{result['name']}」{result['status']}。"
    if "title" in result and "status" in result:
        return f"「{result['title']}」已{result['status']}。"
    if "route" in result:
        return "已准备好跳转页面。"
    if "run_id" in result:
        return f"已启动工作流，运行 ID：{result['run_id'][:8]}。"
    if result.get("deleted") is True and "name" in result:
        return f"项目「{result['name']}」已删除。"
    return "操作完成。"
