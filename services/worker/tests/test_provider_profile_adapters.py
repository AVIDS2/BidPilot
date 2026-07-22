"""Worker adapters must use the shared provider profile resolution boundary."""

from app.adapters import anthropic_llm, llm


def test_openai_worker_adapter_expands_a_deepseek_base_url(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Response:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "draft"}}]}

    def fake_post(url, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return Response()

    monkeypatch.setattr(llm.httpx, "post", fake_post)

    result = llm.draft_section(
        "summary",
        [],
        "project-1",
        provider_config={
            "api_key": "test-key",
            "api_url": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
            "provider_id": "deepseek",
        },
    )

    assert result.content_markdown == "draft"
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"] == {"Authorization": "Bearer test-key", "content-type": "application/json"}


def test_anthropic_worker_adapter_uses_deepseek_anthropic_profile(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Response:
        status_code = 200

        def json(self):
            return {"content": [{"type": "text", "text": "draft"}], "model": "deepseek-v4-flash"}

    def fake_post(url, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return Response()

    monkeypatch.setattr(anthropic_llm.httpx, "post", fake_post)

    result = anthropic_llm.draft_section(
        "summary",
        [],
        "project-1",
        provider_config={
            "api_key": "test-key",
            "api_url": "https://api.deepseek.com/anthropic",
            "model": "deepseek-v4-flash",
            "provider_id": "deepseek-anthropic",
        },
    )

    assert result.content_markdown == "draft"
    assert captured["url"] == "https://api.deepseek.com/anthropic/v1/messages"
    assert captured["headers"] == {
        "x-api-key": "test-key",
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
