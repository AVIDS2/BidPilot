"""Assistant LLM factory tests."""

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from app.agent.llm import get_agent_llm


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
