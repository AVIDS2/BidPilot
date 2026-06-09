"""Chat API request / response schemas."""

from pydantic import BaseModel


class ChatMessage(BaseModel):
    """A single message in a conversation."""

    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Payload for POST /chat/stream."""

    message: str
    project_id: str | None = None
    conversation_id: str | None = None
    conversation_history: list[ChatMessage] = []
    provider_config_id: str | None = None


class ChatConversationRead(BaseModel):
    """Read schema for a conversation summary."""

    id: str
    project_id: str | None
    title: str | None
    created_at: str | None


class ChatHistoryRead(BaseModel):
    """Read schema for chat message history."""

    items: list[ChatMessage]
    total: int


# ── SSE event schemas ──────────────────────────────────────────────────────
# Document the shape of SSE events emitted by POST /chat/stream.


class SSEChatStartEvent(BaseModel):
    """Emitted when the LLM starts generating a response."""

    conversation_id: str
    timestamp: str


class SSEChatContentEvent(BaseModel):
    """Emitted for each text chunk from the LLM."""

    content: str


class SSEChatEndEvent(BaseModel):
    """Emitted when the LLM finishes generating."""

    conversation_id: str
    full_response: str
    timestamp: str


class SSEChatErrorEvent(BaseModel):
    """Emitted when an error occurs during generation."""

    error_message: str
    timestamp: str
