"""Assistant model reasoning-effort wiring tests."""

from __future__ import annotations


def test_assistant_request_accepts_reasoning_effort() -> None:
    from app.assistant.schemas import AssistantRequest

    payload = AssistantRequest(message="帮我看项目", reasoning_effort="ultra")

    assert payload.reasoning_effort == "ultra"


def test_agent_llm_maps_openai_reasoning_effort(monkeypatch) -> None:
    from app.agent import llm as agent_llm

    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(agent_llm, "ChatOpenAI", FakeChatOpenAI)

    agent_llm._make(
        "openai",
        "sk-test",
        "https://api.openai.com/v1",
        "gpt-5.5",
        reasoning_effort="ultra",
    )

    assert captured["reasoning_effort"] == "high"
    assert captured["max_completion_tokens"] == agent_llm.OPERATOR_PLANNER_MAX_OUTPUT_TOKENS


def test_agent_llm_does_not_send_openai_reasoning_to_compatible_gateways(monkeypatch) -> None:
    from app.agent import llm as agent_llm

    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(agent_llm, "ChatOpenAI", FakeChatOpenAI)

    agent_llm._make(
        "openai",
        "sk-test",
        "https://api.deepseek.com/v1",
        "deepseek-chat",
        reasoning_effort="ultra",
    )

    assert "reasoning_effort" not in captured
    assert captured["max_completion_tokens"] == agent_llm.OPERATOR_PLANNER_MAX_OUTPUT_TOKENS


def test_agent_llm_maps_anthropic_reasoning_effort(monkeypatch) -> None:
    from app.agent import llm as agent_llm

    captured: dict[str, object] = {}

    class FakeChatAnthropic:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(agent_llm, "ChatAnthropic", FakeChatAnthropic)

    agent_llm._make(
        "anthropic",
        "sk-ant-test",
        "https://api.anthropic.com",
        "claude-sonnet-4-20250514",
        reasoning_effort="max",
    )

    assert captured["effort"] == "max"
    assert captured["max_tokens_to_sample"] == agent_llm.OPERATOR_PLANNER_MAX_OUTPUT_TOKENS


def test_agent_llm_uses_adaptive_thinking_for_current_official_claude(monkeypatch) -> None:
    from app.agent import llm as agent_llm

    captured: dict[str, object] = {}

    class FakeChatAnthropic:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(agent_llm, "ChatAnthropic", FakeChatAnthropic)

    agent_llm._make(
        "anthropic",
        "sk-ant-test",
        "https://api.anthropic.com",
        "claude-opus-4-8",
        reasoning_effort="high",
    )

    assert captured["thinking"] == {"type": "adaptive"}
    assert captured["effort"] == "high"
    assert captured["temperature"] is None
