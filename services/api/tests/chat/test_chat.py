"""Tests for the chat API endpoints."""

from __future__ import annotations

import json
import uuid

import pytest


def _unique_id() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture
def chat_test_user_id(test_db, default_org_id: str) -> str:
    from app.models import User
    import bcrypt

    user = User(
        id=f"chat-user-{_unique_id()}",
        email=f"chat-{_unique_id()}@example.com",
        display_name="Chat Test User",
        role="admin",
        org_id=default_org_id,
        email_verified=True,
        password_hash=bcrypt.hashpw(b"dummy", bcrypt.gensalt()).decode(),
    )
    test_db.add(user)
    test_db.commit()
    return user.id


@pytest.fixture
def clear_dev_user_chat_state(test_db) -> None:
    from app.models import ChatConversation, ChatMessage

    conversation_ids = [
        row[0]
        for row in test_db.query(ChatConversation.id)
        .filter(ChatConversation.user_id == "dev-user")
        .all()
    ]
    if conversation_ids:
        test_db.query(ChatMessage).filter(
            ChatMessage.conversation_id.in_(conversation_ids)
        ).delete(synchronize_session=False)
    test_db.query(ChatConversation).filter(
        ChatConversation.user_id == "dev-user"
    ).delete(synchronize_session=False)
    test_db.commit()


class TestChatStreamEndpoint:
    """Tests for POST /chat/stream."""

    def test_chat_stream_returns_sse(self, client, clear_dev_user_chat_state):
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

    def test_chat_stream_with_project_id(self, client, test_db, default_org_id: str, clear_dev_user_chat_state):
        """The endpoint accepts an optional project_id."""
        from app.models import Project

        project_id = f"some-project-id-{_unique_id()}"
        project = Project(
            id=project_id,
            slug=f"chat-project-{_unique_id()}",
            name="Chat Test Project",
            scenario_package="bidpilot",
            org_id=default_org_id,
        )
        test_db.add(project)
        test_db.commit()

        response = client.post(
            "/chat/stream",
            json={"message": "Hello", "project_id": project_id},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    def test_chat_stream_with_conversation_history(self, client, clear_dev_user_chat_state):
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

    def test_chat_stream_with_provider_config_id(self, client, clear_dev_user_chat_state):
        """The endpoint accepts an optional provider_config_id."""
        response = client.post(
            "/chat/stream",
            json={"message": "Hello", "provider_config_id": "some-config-id"},
        )
        assert response.status_code == 200


class TestChatConversationsEndpoint:
    """Tests for GET /chat/conversations."""

    def test_list_conversations_empty(self, client, clear_dev_user_chat_state):
        """Returns an empty list when no conversations exist."""
        response = client.get("/chat/conversations")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_conversations_with_project_filter(self, client, clear_dev_user_chat_state):
        """Accepts optional project_id query parameter."""
        response = client.get("/chat/conversations?project_id=some-id")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_conversations_uses_first_message_as_fallback_title(self, client, clear_dev_user_chat_state, monkeypatch):
        monkeypatch.setattr("app.chat.service._resolve_platform_chat_provider", lambda: None)

        response = client.post("/chat/stream", json={"message": "请帮我创建一个新项目"})
        assert response.status_code == 200

        response = client.get("/chat/conversations")
        assert response.status_code == 200
        items = response.json()
        assert items
        assert items[0]["title"] == "请帮我创建一个新项目"

    def test_assistant_stream_can_generate_auto_title(self, client, test_db, clear_dev_user_chat_state, monkeypatch):
        """Assistant sessions should still reuse the conversation title generation flow."""
        from app.chat.service import get_conversation

        monkeypatch.setattr("app.chat.service._generate_conversation_title", lambda *_args, **_kwargs: "平台概览")

        response = client.post("/assistant/stream", json={"message": "给我一个平台状态和最近活动的概览"})
        assert response.status_code == 200

        events = [part for part in response.text.strip().split("\n\n") if part]
        start = next(json.loads(line[6:]) for part in events for line in part.splitlines() if line.startswith("data: ") and "assistant.start" in part)
        conversation = get_conversation(test_db, start["conversation_id"], "dev-user")
        assert conversation is not None
        assert conversation.title == "平台概览"

    def test_rename_conversation(self, client, clear_dev_user_chat_state):
        response = client.post("/chat/stream", json={"message": "请帮我创建一个新项目"})
        assert response.status_code == 200

        conversations = client.get("/chat/conversations").json()
        conversation_id = conversations[0]["id"]

        response = client.patch(
            f"/chat/conversations/{conversation_id}",
            json={"title": "招投标项目初始化"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "招投标项目初始化"

        refreshed = client.get("/chat/conversations").json()
        assert refreshed[0]["title"] == "招投标项目初始化"


class TestChatHistoryEndpoint:
    """Tests for GET /chat/conversations/{id}/messages."""

    def test_history_not_found(self, client):
        """Returns 404 for non-existent conversation."""
        response = client.get("/chat/conversations/nonexistent-id/messages")
        assert response.status_code == 404


class TestChatService:
    """Unit tests for chat service functions."""

    def test_resolve_platform_chat_provider_uses_domestic_env(self, monkeypatch):
        """Official chat should use the unified domestic provider env."""
        import importlib
        from app.chat import service as chat_service

        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.setenv("DOCPILOT_PROVIDER_DOMESTIC_API_KEY", "domestic-test-key")
        monkeypatch.setenv("DOCPILOT_LLM_MODEL_PRIMARY", "deepseek-test-model")

        reloaded = importlib.reload(chat_service)

        provider = reloaded._resolve_platform_chat_provider()
        assert provider is not None
        assert provider.api_key == "domestic-test-key"
        assert provider.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
        assert provider.model == "deepseek-test-model"

    def test_resolve_platform_chat_provider_preserves_deepseek_env(self, monkeypatch):
        """Legacy DeepSeek env should keep using DeepSeek-compatible defaults."""
        import importlib
        from app.chat import service as chat_service

        monkeypatch.delenv("DOCPILOT_PROVIDER_DOMESTIC_API_KEY", raising=False)
        monkeypatch.delenv("ALIYUN_API_KEY", raising=False)
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
        monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
        monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")

        reloaded = importlib.reload(chat_service)

        provider = reloaded._resolve_platform_chat_provider()
        assert provider is not None
        assert provider.api_key == "deepseek-test-key"
        assert provider.base_url == "https://api.deepseek.com/v1"
        assert provider.model == "deepseek-chat"

    def test_resolve_provider_config_explicit_id(self, test_db, chat_test_user_id):
        """Resolves provider config by explicit ID."""
        from app.models import ProviderConfig
        from app.chat.service import _resolve_provider_config

        config = ProviderConfig(
            user_id=chat_test_user_id,
            provider_type="openai",
            api_key="sk-test",
            model="gpt-4o-mini",
            label="Test",
            is_active=False,
        )
        test_db.add(config)
        test_db.commit()
        test_db.refresh(config)

        result = _resolve_provider_config(test_db, chat_test_user_id, config.id)
        assert result is not None
        assert result.id == config.id

    def test_resolve_provider_config_active_fallback(self, test_db, chat_test_user_id):
        """Falls back to active config when no explicit ID given."""
        from app.models import ProviderConfig
        from app.chat.service import _resolve_provider_config

        config = ProviderConfig(
            user_id=chat_test_user_id,
            provider_type="openai",
            api_key="sk-test",
            model="gpt-4o-mini",
            label="Test Active",
            is_active=True,
        )
        test_db.add(config)
        test_db.commit()

        result = _resolve_provider_config(test_db, chat_test_user_id, None)
        assert result is not None
        assert result.label == "Test Active"

    def test_resolve_provider_config_none_when_missing(self, test_db, chat_test_user_id):
        """Returns None when no config exists."""
        from app.chat.service import _resolve_provider_config

        result = _resolve_provider_config(test_db, chat_test_user_id, None)
        assert result is None

    def test_create_conversation(self, test_db, chat_test_user_id):
        """Creates a chat conversation in the database."""
        from app.chat.service import create_conversation

        conv = create_conversation(test_db, chat_test_user_id, None)
        assert conv.id is not None
        assert conv.user_id == chat_test_user_id
        assert conv.project_id is None

    def test_save_message(self, test_db, chat_test_user_id):
        """Saves a message to a conversation."""
        from app.chat.service import create_conversation, save_message

        conv = create_conversation(test_db, chat_test_user_id, None)
        msg = save_message(test_db, conv.id, "user", "Hello!")
        assert msg.conversation_id == conv.id
        assert msg.role == "user"
        assert msg.content == "Hello!"
        test_db.refresh(conv)
        assert conv.title == "Hello!"

    def test_save_first_assistant_message_generates_title(self, test_db, chat_test_user_id, monkeypatch):
        """The first assistant reply upgrades the fallback title to an auto title."""
        from app.chat.service import create_conversation, save_message

        monkeypatch.setattr(
            "app.chat.service._generate_conversation_title",
            lambda *_args, **_kwargs: "自动生成标题",
        )

        conv = create_conversation(test_db, chat_test_user_id, None)
        save_message(test_db, conv.id, "user", "请帮我写一个投标执行摘要")
        save_message(test_db, conv.id, "assistant", "当然，我先帮你整理一个执行摘要结构。")

        test_db.refresh(conv)
        assert conv.title == "自动生成标题"

    def test_manual_conversation_title_is_not_overwritten(self, test_db, chat_test_user_id, monkeypatch):
        """A manual title should win over later auto-generation attempts."""
        from app.chat.service import create_conversation, save_message, rename_conversation

        monkeypatch.setattr(
            "app.chat.service._generate_conversation_title",
            lambda *_args, **_kwargs: "自动生成标题",
        )

        conv = create_conversation(test_db, chat_test_user_id, None)
        save_message(test_db, conv.id, "user", "帮我生成项目计划")
        rename_conversation(test_db, conv.id, chat_test_user_id, "我自己起的标题")
        save_message(test_db, conv.id, "assistant", "好的，我来帮你生成计划。")

        test_db.refresh(conv)
        assert conv.title == "我自己起的标题"

    def test_list_conversations_orders_by_recent_activity(self, test_db, chat_test_user_id):
        """The most recently active conversation should appear first."""
        from app.chat.service import create_conversation, save_message, list_conversations

        first = create_conversation(test_db, chat_test_user_id, None)
        second = create_conversation(test_db, chat_test_user_id, None)

        save_message(test_db, first.id, "user", "older conversation")
        save_message(test_db, second.id, "user", "newer conversation")
        save_message(test_db, first.id, "assistant", "bring me back to top")

        conversations = list_conversations(test_db, chat_test_user_id)
        assert conversations[0].id == first.id

    def test_get_conversation_messages(self, test_db, chat_test_user_id):
        """Retrieves messages for a conversation in order."""
        from app.chat.service import create_conversation, save_message, get_conversation_messages

        conv = create_conversation(test_db, chat_test_user_id, None)
        save_message(test_db, conv.id, "user", "Hello!")
        save_message(test_db, conv.id, "assistant", "Hi there!")
        save_message(test_db, conv.id, "user", "How are you?")

        messages = get_conversation_messages(test_db, conv.id)
        assert len(messages) == 3
        assert messages[0].role == "user"
        assert messages[0].content == "Hello!"
        assert messages[1].role == "assistant"
        assert messages[2].role == "user"

    def test_list_conversations(self, test_db, chat_test_user_id):
        """Lists conversations for a user."""
        from app.chat.service import create_conversation, list_conversations

        create_conversation(test_db, chat_test_user_id, None)
        create_conversation(test_db, chat_test_user_id, None)

        convs = list_conversations(test_db, chat_test_user_id)
        assert len(convs) >= 2

    def test_list_conversations_filtered_by_project(self, test_db, chat_test_user_id, default_org_id: str):
        """Lists conversations filtered by project_id."""
        from app.models import Project
        from app.chat.service import create_conversation, list_conversations

        project_one = Project(
            id=f"proj-1-{_unique_id()}",
            slug=f"chat-proj-one-{_unique_id()}",
            name="Chat Project One",
            scenario_package="bidpilot",
            org_id=default_org_id,
        )
        project_two = Project(
            id=f"proj-2-{_unique_id()}",
            slug=f"chat-proj-two-{_unique_id()}",
            name="Chat Project Two",
            scenario_package="bidpilot",
            org_id=default_org_id,
        )
        test_db.add(project_one)
        test_db.add(project_two)
        test_db.commit()

        create_conversation(test_db, chat_test_user_id, project_one.id)
        create_conversation(test_db, chat_test_user_id, project_two.id)

        convs = list_conversations(test_db, chat_test_user_id, project_id=project_one.id)
        assert convs
        assert all(c.project_id == project_one.id for c in convs)

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
