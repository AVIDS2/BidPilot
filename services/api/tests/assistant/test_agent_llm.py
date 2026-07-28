"""Assistant LLM factory tests."""

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

import pytest

from app.agent.llm import AgentModelConfigurationError, get_agent_llm, resolve_agent_model


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
    from app.agent import llm as agent_llm

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


def test_resolve_agent_model_uses_configured_deepseek_values_without_guessing() -> None:
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
