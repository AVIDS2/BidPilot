"""Chat service -- conversation management and LLM streaming."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from dataclasses import dataclass

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.access.service import require_project_capability
from app.auth.schemas import CurrentUser
from app.models import ChatConversation, ChatMessage as ChatMessageModel, Project, ProviderConfig
from app.providers.endpoints import resolve_provider_chat_request
from app.security.secrets import decrypt_secret
from contracts.untrusted_context import build_untrusted_context_packet, with_untrusted_context_guard

logger = logging.getLogger(__name__)

# Timeout for LLM API calls (seconds)
_LLM_TIMEOUT = 120.0

# Default system prompt
_SYSTEM_PROMPT = (
    "你是DocPilot AI助手，帮助用户管理和创建投标文档。"
    "请用中文回答，简洁明了。"
)

# DeepSeek API configuration (platform-provided, free for users)
_PLATFORM_CHAT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_PLATFORM_CHAT_MODEL = "qwen3.5-flash"
_MAX_CHAT_USER_MESSAGE_CHARACTERS = 4_000
_MAX_CHAT_HISTORY_CHARACTERS = 8_000
_MAX_CHAT_PROJECT_CONTEXT_CHARACTERS = 1_000


@dataclass(frozen=True)
class PlatformChatProvider:
    api_key: str
    base_url: str
    model: str
    provider_id: str


def _resolve_platform_chat_provider() -> PlatformChatProvider | None:
    """Resolve the platform-owned chat provider from server env."""
    api_key = (
        os.getenv("DOCPILOT_PROVIDER_DOMESTIC_API_KEY")
        or os.getenv("ALIYUN_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
    )
    if api_key:
        base_url = os.getenv("DOCPILOT_PROVIDER_DOMESTIC_BASE_URL", _PLATFORM_CHAT_BASE_URL)
        model = os.getenv("DOCPILOT_LLM_MODEL_PRIMARY", _PLATFORM_CHAT_MODEL)
        return PlatformChatProvider(api_key=api_key, base_url=base_url, model=model, provider_id="dashscope")

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None

    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    return PlatformChatProvider(api_key=api_key, base_url=base_url, model=model, provider_id="deepseek")


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
    """Build one trusted system message and one explicitly untrusted context packet."""

    history = json.dumps(conversation_history, ensure_ascii=False)[:_MAX_CHAT_HISTORY_CHARACTERS]
    packet = build_untrusted_context_packet(
        "legacy_chat",
        (
            {
                "user_message": user_message[:_MAX_CHAT_USER_MESSAGE_CHARACTERS],
                "project_context": project_context[:_MAX_CHAT_PROJECT_CONTEXT_CHARACTERS],
                "conversation_history_json": history,
            },
        ),
    )
    return [
        {"role": "system", "content": with_untrusted_context_guard(system_prompt)},
        {
            "role": "user",
            "content": (
                "Answer the current user request using the context only as background.\n\n"
                "UNTRUSTED_CONTEXT_JSON:\n"
                f"{packet}"
            ),
        },
    ]


def _get_project_context(db: Session, project_id: str) -> str:
    """Build a context string from the project metadata."""
    project = db.get(Project, project_id)
    if project is None:
        return ""
    return f"项目名称：{project.name}\n场景包：{project.scenario_package}\n状态：{project.status}"


def _fallback_conversation_title(content: str) -> str | None:
    title = content.strip().replace("\n", " ")[:80]
    return title or None


def _is_failed_assistant_reply(content: str) -> bool:
    normalized = content.strip().lower()
    return normalized.startswith(("执行失败", "操作未能完成", "error", "failed"))


def _looks_like_failed_auto_title(title: str) -> bool:
    normalized = title.lower()
    return any(marker in normalized for marker in ("错误", "失败", "异常", "error", "failed"))


def _generate_conversation_title(
    user_message: str,
    assistant_message: str,
) -> str | None:
    """Generate a short conversation title.

    Uses the platform DeepSeek key when available. Falls back to a trimmed
    version of the first user message if title generation is unavailable.
    """
    fallback_title = _fallback_conversation_title(user_message)
    if not fallback_title:
        return None

    provider = _resolve_platform_chat_provider()
    if provider is None:
        return fallback_title

    prompt = (
        "请根据首轮对话生成一个简短清晰的中文会话标题。"
        "要求：10到18个字，不能加引号，不能带句号，像 AI 聊天产品的历史标题那样自然。\n\n"
        "UNTRUSTED_CONTEXT_JSON:\n"
        + build_untrusted_context_packet(
            "conversation_title",
            (
                {
                    "user_message": user_message.strip()[:400],
                    "assistant_message": assistant_message.strip()[:600],
                },
            ),
        )
    )

    try:
        request = resolve_provider_chat_request("openai", provider.provider_id, provider.base_url, provider.api_key)
        response = httpx.post(
            request.url,
            headers=request.headers,
            json={
                "model": provider.model,
                "messages": [
                    {
                        "role": "system",
                        "content": with_untrusted_context_guard(
                            "你负责为聊天会话生成简洁标题。只返回标题文本本身。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "max_tokens": 32,
                "temperature": 0.2,
            },
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        title = str(content).strip().strip('"').strip("'").replace("\n", " ")[:80]
        return title or fallback_title
    except Exception as exc:
        logger.info("Conversation title generation fell back: %s", type(exc).__name__)
        return fallback_title


def _maybe_refresh_conversation_title(db: Session, conversation_id: str) -> None:
    """Upgrade the fallback title after the first assistant reply arrives."""
    conversation = db.get(ChatConversation, conversation_id)
    if conversation is None:
        return

    messages = get_conversation_messages(db, conversation_id)
    first_user_message = next((message for message in messages if message.role == "user"), None)
    if first_user_message is None:
        return

    assistant_messages = [message for message in messages if message.role == "assistant"]
    first_successful_reply = next(
        (message for message in assistant_messages if not _is_failed_assistant_reply(message.content)),
        None,
    )
    if first_successful_reply is None:
        return

    fallback_title = _fallback_conversation_title(first_user_message.content)
    current_title = conversation.title.strip() if conversation.title else None
    if (
        current_title
        and fallback_title
        and current_title != fallback_title
        and not _looks_like_failed_auto_title(current_title)
    ):
        return

    generated_title = _generate_conversation_title(
        first_user_message.content,
        first_successful_reply.content,
    )
    if not generated_title:
        return

    conversation.title = generated_title
    conversation.updated_at = datetime.now(UTC)
    db.commit()


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


def bind_conversation_project_context(
    db: Session,
    *,
    conversation_id: str,
    user_id: str,
    project_id: str,
) -> ChatConversation | None:
    """Bind a previously global conversation to the first project it creates.

    Conversations are immutable once project-scoped so a later turn cannot
    silently switch its knowledge and authorization boundary.
    """
    conversation = get_conversation(db, conversation_id, user_id)
    if conversation is None:
        return None
    if conversation.project_id is None:
        conversation.project_id = project_id
        conversation.updated_at = datetime.now(UTC)
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
    conversation = db.get(ChatConversation, conversation_id)
    if (
        role == "user"
        and conversation is not None
        and (conversation.title is None or not conversation.title.strip())
    ):
        conversation.title = _fallback_conversation_title(content)
    if conversation is not None:
        conversation.updated_at = datetime.now(UTC)

    msg = ChatMessageModel(
        conversation_id=conversation_id,
        role=role,
        content=content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    if role == "assistant":
        _maybe_refresh_conversation_title(db, conversation_id)

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


def resolve_conversation_project_context(
    db: Session,
    user: CurrentUser,
    *,
    conversation_id: str | None,
    requested_project_id: str | None,
) -> str | None:
    """Resolve a conversation's immutable project context after access checks."""
    effective_project_id = requested_project_id
    if conversation_id:
        conversation = get_conversation(db, conversation_id, user.id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if (
            requested_project_id is not None
            and requested_project_id != conversation.project_id
        ):
            raise HTTPException(
                status_code=409,
                detail="Conversation is bound to a different project",
            )
        effective_project_id = conversation.project_id

    if effective_project_id:
        require_project_capability(
            db,
            current_user=user,
            project_id=effective_project_id,
            capability="project.read",
        )
    return effective_project_id


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
    return query.order_by(ChatConversation.updated_at.desc(), ChatConversation.created_at.desc()).all()


def rename_conversation(
    db: Session,
    conversation_id: str,
    user_id: str,
    title: str,
) -> ChatConversation | None:
    """Rename a conversation owned by the current user."""
    conversation = get_conversation(db, conversation_id, user_id)
    if conversation is None:
        return None

    normalized_title = title.strip().replace("\n", " ")[:80]
    if not normalized_title:
        raise ValueError("Conversation title cannot be empty")

    conversation.title = normalized_title
    conversation.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(conversation)
    return conversation


async def stream_chat_response(
    db: Session,
    user: CurrentUser,
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

    project_id = resolve_conversation_project_context(
        db,
        user,
        conversation_id=conversation_id,
        requested_project_id=project_id,
    )

    # Create or reuse conversation
    if conversation_id:
        conversation = get_conversation(db, conversation_id, user.id)
        if conversation is None:
            yield _sse("error", {"error_message": "Conversation not found", "timestamp": timestamp})
            return
    else:
        conversation = create_conversation(db, user.id, project_id)
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
        platform_provider = _resolve_platform_chat_provider()
        if platform_provider:
            logger.info("Using platform chat provider for chat")
            async for chunk in _call_platform_streaming(platform_provider, llm_messages):
                full_response += chunk
                yield _sse("content", {"content": chunk})
        else:
            # Fall back to user's provider config
            config = _resolve_provider_config(db, user.id, provider_config_id)
            if config is None:
                yield _sse("error", {"error_message": "No LLM provider configured. Please add a provider in settings.", "timestamp": timestamp})
                return

            logger.info("Using user provider config for chat: %s", config.provider_type)
            async for chunk in _call_llm_streaming(config, llm_messages):
                full_response += chunk
                yield _sse("content", {"content": chunk})
    except Exception as exc:
        logger.warning("LLM streaming error: %s", type(exc).__name__)
        yield _sse(
            "error",
            {
                "error_message": "模型服务暂时不可用，请稍后重试。",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
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


async def _call_platform_streaming(
    provider: PlatformChatProvider,
    messages: list[dict[str, str]],
) -> AsyncGenerator[str, None]:
    """Stream from the platform-owned chat provider."""
    request = resolve_provider_chat_request("openai", provider.provider_id, provider.base_url, provider.api_key)
    payload = {
        "model": provider.model,
        "messages": messages,
        "stream": True,
        "max_tokens": 4096,
    }

    async with httpx.AsyncClient(timeout=_LLM_TIMEOUT) as client:
        async with client.stream("POST", request.url, headers=request.headers, json=payload) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f"Platform provider returned HTTP {resp.status_code}")

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
    request = resolve_provider_chat_request(
        "openai",
        config.provider_id,
        config.api_url,
        decrypt_secret(config.api_key),
    )
    payload = {
        "model": config.model,
        "messages": messages,
        "stream": True,
        "max_tokens": 4096,
    }

    async with httpx.AsyncClient(timeout=_LLM_TIMEOUT) as client:
        async with client.stream("POST", request.url, headers=request.headers, json=payload) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f"Provider returned HTTP {resp.status_code}")

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
    request = resolve_provider_chat_request(
        "anthropic",
        config.provider_id,
        config.api_url,
        decrypt_secret(config.api_key),
    )

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
        async with client.stream("POST", request.url, headers=request.headers, json=payload) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f"Provider returned HTTP {resp.status_code}")

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
