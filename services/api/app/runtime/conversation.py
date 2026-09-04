"""Runtime-owned conversation and memory projections for Pi turns.

This module is deliberately independent from the historical Operator graph.
It only projects authorized transcript and memory records into the bounded
context ports consumed by the Pi adapter.  The full database truth remains in
the chat and memory domains; this is an adapter, not a second store.
"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.chat.service import get_recent_conversation_messages
from app.memory.schemas import MemoryContextRead
from app.memory.service import memory_context_for_agent
from app.memory.mem0_provider import (
    mem0_enabled,
    profile_context_records,
    search_profile_memory,
)
from app.models import RuntimeEvent, RuntimeRun

from .model_limits import (
    OPERATOR_PLANNER_MAX_CONVERSATION_MESSAGE_CHARACTERS,
    OPERATOR_PLANNER_MAX_MEMORY_CONTEXT_CHARACTERS,
)
from .prompt_assembly import ConversationContextWindow, compact_conversation_context


MAX_CONVERSATION_SOURCE_MESSAGES = 24


def load_conversation_context(
    db: Session,
    conversation_id: str,
    *,
    exclude_message_id: str | None = None,
) -> ConversationContextWindow:
    """Load a bounded, redacted transcript plus durable terminal replies."""

    messages, history_window_truncated = get_recent_conversation_messages(
        db,
        conversation_id,
        limit=MAX_CONVERSATION_SOURCE_MESSAGES,
    )
    source: list[tuple[float, str, str]] = [
        (
            message.created_at.timestamp() if message.created_at is not None else 0.0,
            message.role,
            _message_with_attachment_context(message),
        )
        for message in messages
        if not exclude_message_id or message.id != exclude_message_id
    ]
    known_contents = {content.strip() for _, _, content in source if content.strip()}
    runtime_messages = (
        db.query(RuntimeEvent)
        .join(RuntimeRun, RuntimeEvent.run_id == RuntimeRun.id)
        .filter(
            RuntimeRun.conversation_id == conversation_id,
            RuntimeEvent.event_type == "message.completed",
        )
        .order_by(RuntimeEvent.created_at.asc(), RuntimeEvent.sequence.asc())
        .limit(MAX_CONVERSATION_SOURCE_MESSAGES + 1)
        .all()
    )
    for event in runtime_messages:
        content = event.public_summary.strip()
        if not content or content in known_contents:
            continue
        known_contents.add(content)
        source.append(
            (
                event.created_at.timestamp() if event.created_at is not None else 0.0,
                "assistant",
                content,
            )
        )
    source.sort(key=lambda item: item[0])
    if len(source) > MAX_CONVERSATION_SOURCE_MESSAGES:
        history_window_truncated = True
        source = source[-MAX_CONVERSATION_SOURCE_MESSAGES:]
    return compact_conversation_context(
        [
            {
                "role": role,
                "content": content[
                    :OPERATOR_PLANNER_MAX_CONVERSATION_MESSAGE_CHARACTERS
                ],
            }
            for _, role, content in source
        ],
        history_window_truncated=history_window_truncated,
    )


def load_authorized_memory(
    db: Session,
    user: CurrentUser,
    *,
    project_id: str | None,
    query: str,
) -> MemoryContextRead | None:
    """Return additive, permission-scoped memory context for a Pi turn."""

    try:
        return memory_context_for_agent(
            db,
            current_user=user,
            project_id=project_id,
            query=query,
            top_k=4,
            max_characters=OPERATOR_PLANNER_MAX_MEMORY_CONTEXT_CHARACTERS,
        )
    except Exception:
        # Memory is an optional context source.  A degraded memory provider
        # must not take down the primary Pi conversation path.
        return None


def memory_context_records(
    memory_context: MemoryContextRead | None,
) -> list[dict[str, Any]]:
    """Convert authorized memory records into Pi model observations."""

    if memory_context is None or not memory_context.items:
        return []
    return [
        {
            "kind": "long_term_memory",
            "scope": item.scope.value,
            "memory_kind": item.kind.value,
            "title": item.title,
            "body_markdown": item.body_markdown,
            "citations": [
                {
                    "source_type": citation.source_type.value,
                    "source_id": citation.source_id,
                    "label": citation.label,
                }
                for citation in item.citations[:3]
            ],
        }
        for item in memory_context.items
    ]


async def load_mem0_profile_context(
    *,
    user_id: str,
    org_id: str,
    query: str,
) -> list[dict[str, Any]]:
    """Recall low-risk profile memory without blocking the Pi event loop."""

    if not mem0_enabled():
        return []

    memories = await asyncio.to_thread(
        search_profile_memory,
        user_id=user_id,
        org_id=org_id,
        query=query,
        top_k=4,
    )
    return profile_context_records(memories)


def _message_with_attachment_context(message: object) -> str:
    content = str(getattr(message, "content", "")).strip()
    attachments = getattr(message, "attachments", ()) or ()
    sections: list[str] = []
    for attachment in attachments:
        text = str(getattr(attachment, "extracted_text", "") or "").strip()
        if not text:
            continue
        name = str(getattr(attachment, "name", "附件"))[:255]
        sections.append(f"历史附件《{name}》可读正文：\n{text}")
    return "\n\n".join([content, *sections]).strip()


__all__ = [
    "MAX_CONVERSATION_SOURCE_MESSAGES",
    "load_authorized_memory",
    "load_conversation_context",
    "load_mem0_profile_context",
    "memory_context_records",
]
