from __future__ import annotations

from types import SimpleNamespace

from app.assistant.tools import web_search_tool


class _Response:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "results": [
                {"title": "公告", "url": "https://example.com/notice", "content": "公开来源"},
            ],
        }


def test_hikari_gateway_uses_bearer_and_appends_search(monkeypatch) -> None:
    captured: dict = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return _Response()

    monkeypatch.setenv("TAVILY_HIKARI_BASE_URL", "https://hikari.example.test/tavily")
    monkeypatch.setenv("TAVILY_HIKARI_TOKEN", "gateway-token")
    monkeypatch.setenv("TAVILY_API_KEY", "official-key-that-must-not-be-used-as-body")
    monkeypatch.setattr("httpx.post", fake_post)

    result = web_search_tool(SimpleNamespace(), SimpleNamespace(), {"query": "常州 招标"})

    assert result.result["provider"] == "tavily_hikari"
    assert captured["url"] == "https://hikari.example.test/tavily/search"
    assert captured["headers"] == {"Authorization": "Bearer gateway-token"}
    assert "api_key" not in captured["json"]


def test_official_tavily_uses_key_in_body(monkeypatch) -> None:
    captured: dict = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return _Response()

    monkeypatch.delenv("TAVILY_HIKARI_BASE_URL", raising=False)
    monkeypatch.delenv("TAVILY_API_BASE_URL", raising=False)
    monkeypatch.delenv("TAVILY_HIKARI_TOKEN", raising=False)
    monkeypatch.setenv("TAVILY_API_KEY", "official-key")
    monkeypatch.setattr("httpx.post", fake_post)

    result = web_search_tool(SimpleNamespace(), SimpleNamespace(), {"query": "常州 招标"})

    assert result.result["provider"] == "tavily"
    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["headers"] == {}
    assert captured["json"]["api_key"] == "official-key"
