"""Chat API request / response schemas."""

from pydantic import BaseModel


class ChatMessageAttachmentRead(BaseModel):
    id: str
    assistant_attachment_id: str | None = None
    document_id: str | None = None
    name: str
    kind: str
    mime_type: str
    size: int
    extraction_status: str
    extraction_error: str | None = None


class ChatMessage(BaseModel):
    """A single message in a conversation."""

    role: str  # "user" or "assistant"
    content: str


class ChatMessageRead(ChatMessage):
    """A persisted message exposed to the conversation surface."""

    id: str
    created_at: str | None
    runtime_run_id: str | None = None
    attachments: list[ChatMessageAttachmentRead] = []


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
    is_pinned: bool = False
    created_at: str | None


class ChatConversationUpdate(BaseModel):
    """Payload for renaming a conversation."""

    title: str | None = None
    is_pinned: bool | None = None


class ChatConversationForkRequest(BaseModel):
    """Create a new durable branch immediately before a user checkpoint."""

    checkpoint_message_id: str


class ChatHistoryRead(BaseModel):
    """Read schema for chat message history."""

    items: list[ChatMessageRead]
    total: int


class ChatConversationForkRead(BaseModel):
    """New branch summary plus the durable prefix copied into it."""

    conversation: ChatConversationRead
    items: list[ChatMessageRead]
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
