"""Assistant model reasoning-effort wiring tests."""

from __future__ import annotations


def test_assistant_request_accepts_reasoning_effort() -> None:
    from app.assistant.schemas import AssistantRequest

    payload = AssistantRequest(message="帮我看项目", reasoning_effort="extra")

    assert payload.reasoning_effort == "extra"


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
        reasoning_effort="extra",
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
        reasoning_effort="extra",
    )

    assert "reasoning_effort" not in captured
    assert captured["max_completion_tokens"] == agent_llm.OPERATOR_PLANNER_MAX_OUTPUT_TOKENS


def test_agent_llm_enables_deepseek_v4_thinking_with_documented_controls(monkeypatch) -> None:
    from app.agent import llm as agent_llm

    captured: dict[str, object] = {}

    class FakeDeepSeekChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(agent_llm, "DeepSeekChatOpenAI", FakeDeepSeekChatOpenAI)

    agent_llm._make(
        "openai",
        "sk-test",
        "https://api.deepseek.com/v1",
        "deepseek-v4-flash",
        provider_id="deepseek",
        reasoning_effort="extra",
    )

    assert captured["reasoning_effort"] == "high"
    assert captured["extra_body"] == {"thinking": {"type": "enabled"}}


def test_agent_llm_uses_only_the_stable_thinking_switch_for_opencode_go_deepseek_v4(monkeypatch) -> None:
    from app.agent import llm as agent_llm

    captured: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(agent_llm, "ChatOpenAI", FakeChatOpenAI)

    agent_llm._make(
        "openai",
        "test-key",
        "https://opencode.ai/zen/go/v1",
        "deepseek-v4-flash",
        provider_id="opencode-go",
        reasoning_effort="high",
    )

    assert captured["extra_body"] == {"thinking": {"type": "enabled"}}
    assert "reasoning_effort" not in captured
    assert captured["temperature"] == 0.7


def test_required_tool_choice_client_disables_deepseek_v4_thinking(monkeypatch) -> None:
    from app.agent import llm as agent_llm

    created: list[dict[str, object]] = []

    class FakeDeepSeekChatOpenAI:
        def __init__(self, **kwargs):
            created.append(kwargs)
            self.openai_api_key = kwargs.get("api_key", "sk-test")
            self.openai_api_base = kwargs.get("base_url", "https://api.deepseek.com/v1")
            self.model_name = kwargs.get("model", "deepseek-v4-flash")
            self.max_tokens = kwargs.get("max_completion_tokens")
            self.max_retries = kwargs.get("max_retries", 2)
            self.request_timeout = kwargs.get("request_timeout")
            self.default_headers = kwargs.get("default_headers")

    monkeypatch.setattr(agent_llm, "DeepSeekChatOpenAI", FakeDeepSeekChatOpenAI)
    source = FakeDeepSeekChatOpenAI(
        api_key="sk-test",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-v4-flash",
        max_completion_tokens=1234,
    )

    action_llm = agent_llm.get_required_tool_choice_llm(source)

    assert isinstance(action_llm, FakeDeepSeekChatOpenAI)
    assert created[-1]["extra_body"] == {"thinking": {"type": "disabled"}}
    assert created[-1]["max_completion_tokens"] == 1234
    assert created[-1]["temperature"] == 0.1


def test_required_tool_choice_client_disables_opencode_go_thinking(monkeypatch) -> None:
    from app.agent import llm as agent_llm

    created: list[dict[str, object]] = []

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            created.append(kwargs)
            self.openai_api_key = kwargs.get("api_key", "sk-test")
            self.openai_api_base = kwargs.get("base_url", "https://opencode.ai/zen/go/v1")
            self.model_name = kwargs.get("model", "deepseek-v4-flash")
            self.max_tokens = kwargs.get("max_completion_tokens")
            self.max_retries = kwargs.get("max_retries", 2)
            self.default_headers = kwargs.get("default_headers")

    monkeypatch.setattr(agent_llm, "ChatOpenAI", FakeChatOpenAI)
    source = FakeChatOpenAI(
        api_key="sk-test",
        base_url="https://opencode.ai/zen/go/v1",
        model="deepseek-v4-flash",
        max_completion_tokens=1234,
    )

    action_llm = agent_llm.get_required_tool_choice_llm(source)

    assert isinstance(action_llm, FakeChatOpenAI)
    assert created[-1]["extra_body"] == {"thinking": {"type": "disabled"}}
    assert created[-1]["max_completion_tokens"] == 1234
    assert created[-1]["temperature"] == 0.7


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
