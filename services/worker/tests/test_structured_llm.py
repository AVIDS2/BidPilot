import pytest

from app.adapters import structured_llm
from app.adapters.provider_errors import ProviderInvocationError


class _Response:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload


def test_openai_compatible_structured_call_normalizes_usage(monkeypatch):
    captured: dict = {}

    def fake_post(_url, **kwargs):
        captured.update(kwargs)
        return _Response(
            {
                "choices": [{"message": {"content": '[{"requirement_text": "Must comply"}]'}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            }
        )

    monkeypatch.setattr(structured_llm.httpx, "post", fake_post)

    result = structured_llm.invoke_structured_text(
        system_prompt="system",
        user_prompt="user",
        provider_config={
            "api_key": "test-key",
            "api_url": "https://example.test/v1/chat/completions",
            "model": "test-openai-model",
        },
        provider_type="openai",
        max_output_tokens=9999,
        temperature=0.1,
    )

    assert result.content.startswith("[")
    assert result.provider_type == "openai"
    assert result.model_used == "test-openai-model"
    assert result.usage is not None
    assert result.usage.total_tokens == 18
    assert captured["json"]["max_tokens"] == 4_096


def test_structured_call_resolves_base_url_and_profile_headers(monkeypatch):
    captured: dict = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _Response({"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(structured_llm.httpx, "post", fake_post)

    structured_llm.invoke_structured_text(
        system_prompt="system",
        user_prompt="user",
        provider_config={
            "api_key": "test-key",
            "api_url": "https://mimo.example.test/v1",
            "model": "mimo-v2.5-pro",
            "provider_id": "mimo",
        },
        provider_type="openai",
        max_output_tokens=100,
        temperature=0.1,
    )

    assert captured["url"] == "https://mimo.example.test/v1/chat/completions"
    assert captured["headers"] == {"api-key": "test-key", "content-type": "application/json"}


def test_anthropic_structured_call_uses_messages_protocol_and_normalizes_usage(monkeypatch):
    captured: dict = {}

    def fake_post(_url, **kwargs):
        captured.update(kwargs)
        return _Response(
            {
                "model": "claude-test",
                "content": [{"type": "text", "text": '{"passed": true}'}],
                "usage": {"input_tokens": 13, "output_tokens": 5},
            }
        )

    monkeypatch.setattr(structured_llm.httpx, "post", fake_post)

    result = structured_llm.invoke_structured_text(
        system_prompt="system",
        user_prompt="user",
        provider_config={
            "api_key": "test-key",
            "api_url": "https://api.anthropic.com/v1/messages",
            "model": "claude-test",
        },
        provider_type="anthropic",
        max_output_tokens=1_500,
        temperature=0.2,
    )

    assert result.content == '{"passed": true}'
    assert result.provider_type == "anthropic"
    assert result.model_used == "claude-test"
    assert result.usage is not None
    assert result.usage.total_tokens == 18
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["json"]["max_tokens"] == 1_500


def test_deleted_structured_provider_is_a_safe_terminal_error(monkeypatch):
    monkeypatch.setattr(structured_llm, "get_provider_by_id", lambda _config_id: None)

    with pytest.raises(ProviderInvocationError) as error:
        structured_llm.resolve_structured_provider("deleted-provider")

    assert error.value.error_code == "provider_config_missing"
    assert error.value.retryable is False
