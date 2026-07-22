from __future__ import annotations

from app.adapters import anthropic_llm, llm


class _Response:
    status_code = 200

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def test_openai_adapter_returns_provider_usage(monkeypatch) -> None:
    monkeypatch.setattr(llm, "_api_key", lambda: "test-key")
    monkeypatch.setattr(llm, "_api_url", lambda: "https://provider.example/v1/chat/completions")
    monkeypatch.setattr(llm, "_api_model", lambda: "provider-model")
    monkeypatch.setattr(
        llm.httpx,
        "post",
        lambda *_args, **_kwargs: _Response(
            {
                "choices": [{"message": {"content": "## Draft"}}],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 6,
                    "total_tokens": 18,
                    "completion_tokens_details": {"reasoning_tokens": 2},
                },
            }
        ),
    )

    result = llm.draft_section("summary", [], "project-1")

    assert result.usage is not None
    assert result.usage.total_tokens == 18
    assert result.usage.reasoning_tokens == 2


def test_anthropic_adapter_returns_provider_usage(monkeypatch) -> None:
    monkeypatch.setattr(anthropic_llm, "_api_key", lambda: "test-key")
    monkeypatch.setattr(anthropic_llm, "_api_url", lambda: "https://provider.example/v1/messages")
    monkeypatch.setattr(anthropic_llm, "_api_model", lambda: "provider-model")
    monkeypatch.setattr(
        anthropic_llm.httpx,
        "post",
        lambda *_args, **_kwargs: _Response(
            {
                "content": [{"type": "text", "text": "## Draft"}],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 7,
                    "cache_read_input_tokens": 3,
                    "cache_creation_input_tokens": 4,
                },
            }
        ),
    )

    result = anthropic_llm.draft_section("summary", [], "project-1")

    assert result.usage is not None
    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 7
    assert result.usage.cache_read_tokens == 3
    assert result.usage.cache_write_tokens == 4


def test_anthropic_adapter_uses_adaptive_thinking_without_temperature_for_new_models(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(anthropic_llm, "_api_key", lambda: "test-key")
    monkeypatch.setattr(anthropic_llm, "_api_url", lambda: "https://api.anthropic.com/v1/messages")
    monkeypatch.setattr(anthropic_llm, "_api_model", lambda: "claude-opus-4-8")
    monkeypatch.setattr(
        anthropic_llm.httpx,
        "post",
        lambda _url, **kwargs: (
            captured.update(kwargs["json"])
            or _Response({"content": [{"type": "text", "text": "## Draft"}], "usage": {}})
        ),
    )

    anthropic_llm.draft_section("summary", [], "project-1", reasoning_effort="max")

    assert captured["max_tokens"] == anthropic_llm._MAX_RESPONSE_TOKENS
    assert captured["thinking"] == {"type": "adaptive"}
    assert captured["output_config"] == {"effort": "max"}
    assert "temperature" not in captured


def test_anthropic_adapter_keeps_bounded_manual_thinking_for_older_models(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(anthropic_llm, "_api_key", lambda: "test-key")
    monkeypatch.setattr(anthropic_llm, "_api_url", lambda: "https://api.anthropic.com/v1/messages")
    monkeypatch.setattr(anthropic_llm, "_api_model", lambda: "claude-sonnet-4-20250514")
    monkeypatch.setattr(
        anthropic_llm.httpx,
        "post",
        lambda _url, **kwargs: (
            captured.update(kwargs["json"])
            or _Response({"content": [{"type": "text", "text": "## Draft"}], "usage": {}})
        ),
    )

    anthropic_llm.draft_section("summary", [], "project-1", reasoning_effort="max")

    assert captured["max_tokens"] == anthropic_llm._MAX_RESPONSE_TOKENS
    assert captured["thinking"] == {
        "type": "enabled",
        "budget_tokens": anthropic_llm._THINKING_BUDGETS["max"],
    }
    assert captured["temperature"] == 0.3
