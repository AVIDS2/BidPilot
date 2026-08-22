"""Assistant LLM factory tests."""

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

import pytest

from app.agent.llm import (
    AgentModelConfigurationError,
    DeepSeekChatOpenAI,
    get_agent_llm,
    resolve_agent_model,
)


def test_agent_llm_uses_openai_compatible_provider() -> None:
    llm = get_agent_llm(
        provider_type="openai",
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
    )

    assert isinstance(llm, ChatOpenAI)


def test_agent_llm_uses_anthropic_messages_provider() -> None:
    llm = get_agent_llm(
        provider_type="anthropic",
        api_key="sk-ant-test",
        base_url="https://gateway.example.com/anthropic/v1/messages",
        model="claude-sonnet-4-20250514",
    )

    assert isinstance(llm, ChatAnthropic)


def test_agent_llm_adds_profile_header_for_mimo(monkeypatch) -> None:
    from app.runtime import model_impl as agent_llm

    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(agent_llm, "ChatOpenAI", FakeChatOpenAI)

    agent_llm._make(
        "openai",
        "test-mimo-key",
        "https://mimo.example.test/v1",
        "mimo-v2.5-pro",
        provider_id="mimo",
    )

    assert captured["base_url"] == "https://mimo.example.test/v1"
    assert captured["default_headers"] == {"api-key": "test-mimo-key"}


def test_resolve_agent_model_requires_an_explicit_platform_model() -> None:
    with pytest.raises(AgentModelConfigurationError, match="尚未配置"):
        resolve_agent_model(environment={})


def test_resolve_agent_model_uses_configured_deepseek_values() -> None:
    resolved = resolve_agent_model(
        environment={
            "DEEPSEEK_API_KEY": "test-key",
            "DEEPSEEK_BASE_URL": "https://gateway.example.test/v1",
            "DEEPSEEK_MODEL": "deepseek-v4-flash",
        }
    )

    assert resolved.provider_type == "openai"
    assert resolved.provider_id == "deepseek"
    assert resolved.base_url == "https://gateway.example.test/v1"
    assert resolved.model == "deepseek-v4-flash"


def test_resolve_agent_model_uses_the_supported_deepseek_default() -> None:
    resolved = resolve_agent_model(environment={"DEEPSEEK_API_KEY": "test-key"})

    assert resolved.provider_type == "openai"
    assert resolved.provider_id == "deepseek"
    assert resolved.base_url == "https://api.deepseek.com/v1"
    assert resolved.model == "deepseek-v4-flash"


def test_resolve_agent_model_prefers_opencode_go_when_its_platform_key_is_configured() -> None:
    resolved = resolve_agent_model(
        environment={
            "OPENCODE_API_KEY": "test-opencode-key",
            "DEEPSEEK_API_KEY": "test-deepseek-key",
        }
    )

    assert resolved.provider_type == "openai"
    assert resolved.provider_id == "opencode-go"
    assert resolved.base_url == "https://opencode.ai/zen/go/v1"
    assert resolved.model == "deepseek-v4-flash"


def test_resolve_agent_model_uses_opencode_defaults_for_explicit_assistant_profile() -> None:
    resolved = resolve_agent_model(
        environment={
            "DOCPILOT_ASSISTANT_API_KEY": "platform-key",
            "DOCPILOT_ASSISTANT_PROVIDER_ID": "opencode-go",
        }
    )

    assert resolved.provider_id == "opencode-go"
    assert resolved.base_url == "https://opencode.ai/zen/go/v1"
    assert resolved.model == "deepseek-v4-flash"


def test_deepseek_client_preserves_visible_reasoning_content() -> None:
    from langchain_core.messages import AIMessageChunk

    llm = DeepSeekChatOpenAI(
        api_key="test-key",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-v4-flash",
    )

    result = llm._convert_chunk_to_generation_chunk(
        {
            "choices": [
                {
                    "delta": {
                        "role": "assistant",
                        "content": "",
                        "reasoning_content": "先读取项目上下文。",
                    }
                }
            ]
        },
        AIMessageChunk,
        None,
    )

    assert result is not None
    assert result.message.additional_kwargs["reasoning_content"] == "先读取项目上下文。"
