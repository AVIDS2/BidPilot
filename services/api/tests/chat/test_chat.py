"""Tests for the chat API endpoints."""

from __future__ import annotations

import json

import pytest


class TestChatStreamEndpoint:
    """Tests for POST /chat/stream."""

    def test_chat_stream_returns_sse(self, client):
        """The endpoint returns a streaming SSE response."""
        response = client.post(
            "/chat/stream",
            json={"message": "Hello"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    def test_chat_stream_requires_message(self, client):
        """The endpoint requires a message field."""
        response = client.post("/chat/stream", json={})
        assert response.status_code == 422

    def test_chat_stream_with_project_id(self, client):
        """The endpoint accepts an optional project_id."""
        response = client.post(
            "/chat/stream",
            json={"message": "Hello", "project_id": "some-project-id"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    def test_chat_stream_with_conversation_history(self, client):
        """The endpoint accepts conversation history."""
        response = client.post(
            "/chat/stream",
            json={
                "message": "What is this?",
                "conversation_history": [
                    {"role": "user", "content": "Hi"},
                    {"role": "assistant", "content": "Hello!"},
                ],
            },
        )
        assert response.status_code == 200

    def test_chat_stream_with_provider_config_id(self, client):
        """The endpoint accepts an optional provider_config_id."""
        response = client.post(
            "/chat/stream",
            json={"message": "Hello", "provider_config_id": "some-config-id"},
        )
        assert response.status_code == 200


class TestChatConversationsEndpoint:
    """Tests for GET /chat/conversations."""

    def test_list_conversations_empty(self, client):
        """Returns an empty list when no conversations exist."""
        response = client.get("/chat/conversations")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_conversations_with_project_filter(self, client):
        """Accepts optional project_id query parameter."""
        response = client.get("/chat/conversations?project_id=some-id")
        assert response.status_code == 200
        assert response.json() == []


class TestChatHistoryEndpoint:
    """Tests for GET /chat/conversations/{id}/messages."""

    def test_history_not_found(self, client):
        """Returns 404 for non-existent conversation."""
        response = client.get("/chat/conversations/nonexistent-id/messages")
        assert response.status_code == 404


class TestChatService:
    """Unit tests for chat service functions."""

    def test_resolve_provider_config_explicit_id(self, test_db, default_user_id):
        """Resolves provider config by explicit ID."""
        from app.models import ProviderConfig
        from app.chat.service import _resolve_provider_config

        config = ProviderConfig(
            user_id=default_user_id,
            provider_type="openai",
            api_key="sk-test",
            model="gpt-4o-mini",
            label="Test",
            is_active=False,
        )
        test_db.add(config)
        test_db.commit()
        test_db.refresh(config)

        result = _resolve_provider_config(test_db, default_user_id, config.id)
        assert result is not None
        assert result.id == config.id

    def test_resolve_provider_config_active_fallback(self, test_db, default_user_id):
        """Falls back to active config when no explicit ID given."""
        from app.models import ProviderConfig
        from app.chat.service import _resolve_provider_config

        config = ProviderConfig(
            user_id=default_user_id,
            provider_type="openai",
            api_key="sk-test",
            model="gpt-4o-mini",
            label="Test Active",
            is_active=True,
        )
        test_db.add(config)
        test_db.commit()

        result = _resolve_provider_config(test_db, default_user_id, None)
        assert result is not None
        assert result.label == "Test Active"

    def test_resolve_provider_config_none_when_missing(self, test_db, default_user_id):
        """Returns None when no config exists."""
        from app.chat.service import _resolve_provider_config

        result = _resolve_provider_config(test_db, default_user_id, None)
        assert result is None

    def test_create_conversation(self, test_db, default_user_id):
        """Creates a chat conversation in the database."""
        from app.chat.service import create_conversation

        conv = create_conversation(test_db, default_user_id, None)
        assert conv.id is not None
        assert conv.user_id == default_user_id
        assert conv.project_id is None

    def test_save_message(self, test_db, default_user_id):
        """Saves a message to a conversation."""
        from app.chat.service import create_conversation, save_message

        conv = create_conversation(test_db, default_user_id, None)
        msg = save_message(test_db, conv.id, "user", "Hello!")
        assert msg.conversation_id == conv.id
        assert msg.role == "user"
        assert msg.content == "Hello!"

    def test_get_conversation_messages(self, test_db, default_user_id):
        """Retrieves messages for a conversation in order."""
        from app.chat.service import create_conversation, save_message, get_conversation_messages

        conv = create_conversation(test_db, default_user_id, None)
        save_message(test_db, conv.id, "user", "Hello!")
        save_message(test_db, conv.id, "assistant", "Hi there!")
        save_message(test_db, conv.id, "user", "How are you?")

        messages = get_conversation_messages(test_db, conv.id)
        assert len(messages) == 3
        assert messages[0].role == "user"
        assert messages[0].content == "Hello!"
        assert messages[1].role == "assistant"
        assert messages[2].role == "user"

    def test_list_conversations(self, test_db, default_user_id):
        """Lists conversations for a user."""
        from app.chat.service import create_conversation, list_conversations

        create_conversation(test_db, default_user_id, None)
        create_conversation(test_db, default_user_id, None)

        convs = list_conversations(test_db, default_user_id)
        assert len(convs) >= 2

    def test_list_conversations_filtered_by_project(self, test_db, default_user_id):
        """Lists conversations filtered by project_id."""
        from app.chat.service import create_conversation, list_conversations

        create_conversation(test_db, default_user_id, "proj-1")
        create_conversation(test_db, default_user_id, "proj-2")

        convs = list_conversations(test_db, default_user_id, project_id="proj-1")
        assert all(c.project_id == "proj-1" for c in convs)

    def test_build_messages(self):
        """Builds the messages array correctly."""
        from app.chat.service import _build_messages

        messages = _build_messages(
            system_prompt="You are helpful.",
            project_context="Project: Test",
            conversation_history=[{"role": "user", "content": "Hi"}],
            user_message="Hello",
        )
        assert messages[0]["role"] == "system"
        assert "You are helpful" in messages[0]["content"]
        assert "Project: Test" in messages[0]["content"]
        assert messages[1] == {"role": "user", "content": "Hi"}
        assert messages[2] == {"role": "user", "content": "Hello"}

    def test_sse_format(self):
        """SSE output format is correct."""
        from app.chat.service import _sse

        result = _sse("content", {"content": "hello"})
        assert result.startswith("event: content\n")
        assert "data: " in result
        assert result.endswith("\n\n")
        # Verify JSON is parseable
        data_line = result.split("\n")[1]
        json_str = data_line[6:]  # strip "data: "
        parsed = json.loads(json_str)
        assert parsed["content"] == "hello"
