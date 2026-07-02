"""Translate LangGraph astream_events to SSE events for the frontend."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_agent_events(
    agent,
    messages: list,
    config: dict,
    conversation_id: str,
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

            # Tool execution completed
            elif kind == "on_tool_end":
                tool_name = event.get("name", "") or current_tool_name
                output = event.get("data", {}).get("output", "")

                # Parse tool output
                result = {}
                summary = ""
                if isinstance(output, str):
                    try:
                        result = json.loads(output)
                        summary = _extract_summary(tool_name, result)
                    except (json.JSONDecodeError, TypeError):
                        summary = output[:200]
                else:
                    summary = str(output)[:200] if output else ""

                confirmation_payload = _extract_confirmation_request(tool_name, result)
                if confirmation_payload is not None:
                    awaiting_confirmation = True
                    yield _sse("assistant.confirmation_requested", confirmation_payload)
                    current_tool_name = None
                    continue

                yield _sse("assistant.tool_succeeded", {
                    "tool_name": tool_name,
                    "result": result,
                    "summary": summary,
                    "state": "completed",
                })
                current_tool_name = None

    except Exception as exc:
        yield _sse("assistant.tool_failed", {
            "tool_name": current_tool_name or "unknown",
            "error_message": str(exc),
            "state": "failed",
        })

    yield _sse("assistant.end", {
        "conversation_id": conversation_id,
        "state": "needs_confirmation" if awaiting_confirmation else "completed",
    })


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
