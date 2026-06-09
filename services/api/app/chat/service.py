"""Chat service -- conversation management and LLM streaming."""

from __future__ import annotations

import json
import logging
import os
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from app.models import ChatConversation, ChatMessage as ChatMessageModel, Project, ProviderConfig

logger = logging.getLogger(__name__)

# Timeout for LLM API calls (seconds)
_LLM_TIMEOUT = 120.0

# Default system prompt
_SYSTEM_PROMPT = (
    "你是DocPilot AI助手，帮助用户管理和创建投标文档。"
    "请用中文回答，简洁明了。"
)

# DeepSeek API configuration (platform-provided, free for users)
_DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
_DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
_DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


def _resolve_provider_config(
    db: Session,
    user_id: str,
    provider_config_id: str | None,
) -> ProviderConfig | None:
    """Resolve the active provider config for the user.

    Priority:
    1. Explicit provider_config_id
    2. Active config of any type
    """
    if provider_config_id:
        config = db.query(ProviderConfig).filter(
            ProviderConfig.id == provider_config_id,
            ProviderConfig.user_id == user_id,
        ).first()
        if config is not None:
            return config

    # Fall back to any active config
    return (
        db.query(ProviderConfig)
        .filter(ProviderConfig.user_id == user_id, ProviderConfig.is_active.is_(True))
        .first()
    )


def _build_messages(
    system_prompt: str,
    project_context: str,
    conversation_history: list[dict[str, str]],
    user_message: str,
) -> list[dict[str, str]]:
    """Build the messages array for the LLM API call."""
    system = system_prompt
    if project_context:
        system += f"\n\n当前项目上下文：\n{project_context}"

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})
    return messages


def _get_project_context(db: Session, project_id: str) -> str:
    """Build a context string from the project metadata."""
    project = db.get(Project, project_id)
    if project is None:
        return ""
    return f"项目名称：{project.name}\n场景包：{project.scenario_package}\n状态：{project.status}"


def create_conversation(
    db: Session,
    user_id: str,
    project_id: str | None,
) -> ChatConversation:
    """Create a new chat conversation."""
    conversation = ChatConversation(
        user_id=user_id,
        project_id=project_id,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def save_message(
    db: Session,
    conversation_id: str,
    role: str,
    content: str,
) -> ChatMessageModel:
    """Persist a chat message."""
    msg = ChatMessageModel(
        conversation_id=conversation_id,
        role=role,
        content=content,
    )
    db.add(msg)
    db.commit()
    return msg


def get_conversation(
    db: Session,
    conversation_id: str,
    user_id: str,
) -> ChatConversation | None:
    """Get a conversation by ID, scoped to user."""
    return db.query(ChatConversation).filter(
        ChatConversation.id == conversation_id,
        ChatConversation.user_id == user_id,
    ).first()


def get_conversation_messages(
    db: Session,
    conversation_id: str,
) -> list[ChatMessageModel]:
    """Get all messages for a conversation, ordered by creation time."""
    return (
        db.query(ChatMessageModel)
        .filter(ChatMessageModel.conversation_id == conversation_id)
        .order_by(ChatMessageModel.created_at.asc())
        .all()
    )


def list_conversations(
    db: Session,
    user_id: str,
    project_id: str | None = None,
) -> list[ChatConversation]:
    """List conversations for a user, optionally filtered by project."""
    query = db.query(ChatConversation).filter(ChatConversation.user_id == user_id)
    if project_id:
        query = query.filter(ChatConversation.project_id == project_id)
    return query.order_by(ChatConversation.created_at.desc()).all()


async def stream_chat_response(
    db: Session,
    user_id: str,
    message: str,
    project_id: str | None,
    conversation_history: list[dict[str, str]],
    provider_config_id: str | None,
    conversation_id: str | None,
) -> AsyncGenerator[str, None]:
    """Async generator yielding SSE event strings for a chat response.

    This is the core streaming logic. It:
    1. Resolves the LLM provider config (DeepSeek platform-provided first, then user config)
    2. Creates or reuses a conversation
    3. Saves the user message
    4. Calls the LLM API with streaming
    5. Yields SSE events as text chunks arrive
    6. Saves the full assistant response
    """
    from datetime import UTC, datetime

    timestamp = datetime.now(UTC).isoformat()

    # Create or reuse conversation
    if conversation_id:
        conversation = get_conversation(db, conversation_id, user_id)
        if conversation is None:
            yield _sse("error", {"error_message": "Conversation not found", "timestamp": timestamp})
            return
    else:
        conversation = create_conversation(db, user_id, project_id)
        conversation_id = conversation.id

    # Save user message
    save_message(db, conversation_id, "user", message)

    # Build context
    project_context = ""
    if project_id:
        project_context = _get_project_context(db, project_id)

    llm_messages = _build_messages(
        _SYSTEM_PROMPT,
        project_context,
        conversation_history,
        message,
    )

    # Emit start event
    yield _sse("start", {"conversation_id": conversation_id, "timestamp": timestamp})

    # Call LLM with streaming - Priority: DeepSeek (platform free) > User provider config
    full_response = ""
    try:
        # Try DeepSeek first (platform-provided, free for users)
        if _DEEPSEEK_API_KEY:
            logger.info("Using DeepSeek API for chat (platform-provided)")
            async for chunk in _call_deepseek_streaming(llm_messages):
                full_response += chunk
                yield _sse("content", {"content": chunk})
        else:
            # Fall back to user's provider config
            config = _resolve_provider_config(db, user_id, provider_config_id)
            if config is None:
                yield _sse("error", {"error_message": "No LLM provider configured. Please add a provider in settings.", "timestamp": timestamp})
                return

            logger.info("Using user provider config for chat: %s", config.provider_type)
            async for chunk in _call_llm_streaming(config, llm_messages):
                full_response += chunk
                yield _sse("content", {"content": chunk})
    except Exception as exc:
        logger.error("LLM streaming error: %s", exc, exc_info=True)
        yield _sse("error", {"error_message": str(exc), "timestamp": datetime.now(UTC).isoformat()})
        return

    # Save assistant message
    if full_response:
        save_message(db, conversation_id, "assistant", full_response)

    # Emit end event
    yield _sse("end", {
        "conversation_id": conversation_id,
        "full_response": full_response,
        "timestamp": datetime.now(UTC).isoformat(),
    })


async def _call_deepseek_streaming(
    messages: list[dict[str, str]],
) -> AsyncGenerator[str, None]:
    """Stream from DeepSeek API (platform-provided, free for users)."""
    url = f"{_DEEPSEEK_BASE_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {_DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": _DEEPSEEK_MODEL,
        "messages": messages,
        "stream": True,
        "max_tokens": 4096,
    }

    async with httpx.AsyncClient(timeout=_LLM_TIMEOUT) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise RuntimeError(f"DeepSeek API error {resp.status_code}: {body.decode()[:500]}")

            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    return
                try:
                    data = json.loads(data_str)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue


async def _call_llm_streaming(
    config: ProviderConfig,
    messages: list[dict[str, str]],
) -> AsyncGenerator[str, None]:
    """Call the LLM API with streaming and yield text chunks.

    Supports both OpenAI-compatible and Anthropic APIs.
    """
    if config.provider_type == "anthropic":
        async for chunk in _call_anthropic_streaming(config, messages):
            yield chunk
    else:
        async for chunk in _call_openai_streaming(config, messages):
            yield chunk


async def _call_openai_streaming(
    config: ProviderConfig,
    messages: list[dict[str, str]],
) -> AsyncGenerator[str, None]:
    """Stream from an OpenAI-compatible API."""
    url = (config.api_url or "https://api.openai.com/v1/chat/completions").rstrip("/")
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.model,
        "messages": messages,
        "stream": True,
        "max_tokens": 4096,
    }

    async with httpx.AsyncClient(timeout=_LLM_TIMEOUT) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise RuntimeError(f"LLM API error {resp.status_code}: {body.decode()[:500]}")

            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    return
                try:
                    data = json.loads(data_str)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue


async def _call_anthropic_streaming(
    config: ProviderConfig,
    messages: list[dict[str, str]],
) -> AsyncGenerator[str, None]:
    """Stream from the Anthropic Messages API."""
    url = (config.api_url or "https://api.anthropic.com/v1/messages").rstrip("/")
    headers = {
        "x-api-key": config.api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    # Anthropic uses separate system parameter
    system_text = ""
    api_messages = []
    for msg in messages:
        if msg["role"] == "system":
            system_text = msg["content"]
        else:
            api_messages.append(msg)

    payload: dict = {
        "model": config.model,
        "messages": api_messages,
        "max_tokens": 4096,
        "stream": True,
    }
    if system_text:
        payload["system"] = system_text

    async with httpx.AsyncClient(timeout=_LLM_TIMEOUT) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise RuntimeError(f"Anthropic API error {resp.status_code}: {body.decode()[:500]}")

            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                try:
                    data = json.loads(data_str)
                    if data.get("type") == "content_block_delta":
                        text = data.get("delta", {}).get("text")
                        if text:
                            yield text
                    elif data.get("type") == "message_stop":
                        return
                except (json.JSONDecodeError, KeyError):
                    continue


def _sse(event: str, data: dict) -> str:
    """Format an SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
