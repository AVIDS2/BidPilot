"""Provider profile contract tests shared by API and Worker runtimes."""

from contracts.provider_profiles import (
    infer_provider_id,
    resolve_provider_chat_request,
    resolve_provider_model_list_request,
)


def test_deepseek_anthropic_profile_resolves_documented_messages_endpoint() -> None:
    request = resolve_provider_chat_request(
        "anthropic",
        "deepseek-anthropic",
        "https://api.deepseek.com/anthropic",
        "test-key",
    )

    assert request.url == "https://api.deepseek.com/anthropic/v1/messages"
    assert request.headers["x-api-key"] == "test-key"
    assert request.headers["anthropic-version"] == "2023-06-01"


def test_mimo_profile_uses_its_documented_api_key_header() -> None:
    request = resolve_provider_chat_request(
        "openai",
        "mimo",
        "https://mimo.example.test/v1",
        "test-key",
    )

    assert request.url == "https://mimo.example.test/v1/chat/completions"
    assert request.headers["api-key"] == "test-key"
    assert "Authorization" not in request.headers


def test_manual_model_profiles_do_not_probe_an_undocumented_models_endpoint() -> None:
    request = resolve_provider_model_list_request(
        "openai",
        "dashscope",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "test-key",
    )

    assert request is None


def test_deepseek_anthropic_model_discovery_uses_deepseek_model_api() -> None:
    request = resolve_provider_model_list_request(
        "anthropic",
        "deepseek-anthropic",
        "https://api.deepseek.com/anthropic",
        "test-key",
    )

    assert request is not None
    assert request.url == "https://api.deepseek.com/models"
    assert request.headers == {"Authorization": "Bearer test-key"}


def test_infer_provider_profile_preserves_unknown_gateway_protocol() -> None:
    assert infer_provider_id("openai", "https://gateway.example.test/v1") == "custom-openai"
    assert infer_provider_id("anthropic", "https://gateway.example.test/v1") == "custom-anthropic"
