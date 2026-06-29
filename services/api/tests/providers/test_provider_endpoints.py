"""Provider endpoint normalization tests."""

from app.providers.endpoints import normalize_provider_base_url, normalize_provider_endpoint


def test_normalize_openai_endpoint_accepts_base_url() -> None:
    assert (
        normalize_provider_endpoint("openai", "https://api.deepseek.com")
        == "https://api.deepseek.com/v1/chat/completions"
    )
    assert (
        normalize_provider_endpoint("openai", "https://api.deepseek.com/v1")
        == "https://api.deepseek.com/v1/chat/completions"
    )
    assert (
        normalize_provider_endpoint("openai", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    )


def test_normalize_openai_endpoint_keeps_full_endpoint() -> None:
    assert (
        normalize_provider_endpoint("openai", "https://openrouter.ai/api/v1/chat/completions")
        == "https://openrouter.ai/api/v1/chat/completions"
    )


def test_normalize_anthropic_endpoint_accepts_base_url() -> None:
    assert (
        normalize_provider_endpoint("anthropic", "https://api.anthropic.com")
        == "https://api.anthropic.com/v1/messages"
    )
    assert (
        normalize_provider_endpoint("anthropic", "https://gateway.example.com/anthropic/v1")
        == "https://gateway.example.com/anthropic/v1/messages"
    )


def test_normalize_anthropic_endpoint_keeps_full_endpoint() -> None:
    assert (
        normalize_provider_endpoint("anthropic", "https://gateway.example.com/anthropic/v1/messages")
        == "https://gateway.example.com/anthropic/v1/messages"
    )


def test_normalize_langchain_base_urls() -> None:
    assert normalize_provider_base_url("openai", "https://api.deepseek.com") == "https://api.deepseek.com/v1"
    assert (
        normalize_provider_base_url("openai", "https://api.deepseek.com/v1/chat/completions")
        == "https://api.deepseek.com/v1"
    )
    assert normalize_provider_base_url("anthropic", "https://api.anthropic.com/v1") == "https://api.anthropic.com"
    assert (
        normalize_provider_base_url("anthropic", "https://gateway.example.com/anthropic/v1/messages")
        == "https://gateway.example.com/anthropic"
    )
