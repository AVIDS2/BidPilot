"""Chat API router -- streaming AI conversation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db
from app.models import ChatConversation, ChatMessage as ChatMessageModel

from .schemas import ChatConversationRead, ChatConversationUpdate, ChatHistoryRead, ChatMessage, ChatRequest
from .service import (
    get_conversation,
    get_conversation_messages,
    list_conversations,
    rename_conversation,
    stream_chat_response,
)

router = APIRouter(prefix="/chat", tags=["chat"])


def _conversation_title(db: Session, conversation_id: str, stored_title: str | None) -> str | None:
    if stored_title and stored_title.strip():
        return stored_title
    first_user_message = (
        db.query(ChatMessageModel.content)
        .filter(
            ChatMessageModel.conversation_id == conversation_id,
            ChatMessageModel.role == "user",
        )
        .order_by(ChatMessageModel.created_at.asc())
        .first()
    )
    if first_user_message is None:
        return None
    return first_user_message[0].strip().replace("\n", " ")[:80] or None


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Stream an AI chat response via Server-Sent Events.

    The request body contains the user message, optional project context,
    optional conversation history (for multi-turn), and optional provider
    config ID.

    SSE event types:

    - ``start``: generation begins, includes conversation_id
    - ``content``: a text chunk from the LLM
    - ``end``: generation complete, includes full_response
    - ``error``: an error occurred

    If ``conversation_id`` is provided in the payload, the message is
    appended to an existing conversation.  Otherwise a new conversation
    is created.
    """
    history = [{"role": m.role, "content": m.content} for m in payload.conversation_history]

    return StreamingResponse(
        stream_chat_response(
            db=db,
            user_id=user.id,
            message=payload.message,
            project_id=payload.project_id,
            conversation_history=history,
            provider_config_id=payload.provider_config_id,
            conversation_id=payload.conversation_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations", response_model=list[ChatConversationRead])
def list_chat_conversations(
    project_id: str | None = Query(None),
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """List the current user's chat conversations.

    Optionally filter by project_id.
    """
    conversations = list_conversations(db, user.id, project_id)
    return [
        ChatConversationRead(
            id=c.id,
            project_id=c.project_id,
            title=_conversation_title(db, c.id, c.title),
            created_at=c.created_at.isoformat() if c.created_at else None,
        )
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}/messages", response_model=ChatHistoryRead)
def get_chat_history(
    conversation_id: str,
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Get the message history for a conversation."""
    conversation = get_conversation(db, conversation_id, user.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = get_conversation_messages(db, conversation_id)
    return ChatHistoryRead(
        items=[ChatMessage(role=m.role, content=m.content) for m in messages],
        total=len(messages),
    )


@router.patch("/conversations/{conversation_id}", response_model=ChatConversationRead)
def update_chat_conversation(
    conversation_id: str,
    payload: ChatConversationUpdate,
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Rename a chat conversation."""
    try:
        conversation = rename_conversation(db, conversation_id, user.id, payload.title)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ChatConversationRead(
        id=conversation.id,
        project_id=conversation.project_id,
        title=conversation.title,
        created_at=conversation.created_at.isoformat() if conversation.created_at else None,
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_chat_conversation(
    conversation_id: str,
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Delete a chat conversation owned by the current user."""
    conversation = get_conversation(db, conversation_id, user.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conversation)
    db.commit()
