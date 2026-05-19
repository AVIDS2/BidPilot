"""Test Anthropic/Claude LLM adapter."""
from unittest.mock import patch, MagicMock
from app.adapters.anthropic_llm import draft_section


def test_anthropic_draft_returns_stub_without_key():
    """Without ANTHROPIC_API_KEY, should return structured stub."""
    result = draft_section("intro", ["Some evidence text"], "proj-1")
    assert result.content_markdown is not None
    assert "stub" in result.model_used
    assert "intro" in result.content_markdown.lower()


def test_anthropic_draft_includes_evidence_in_stub():
    """Stub output should include evidence text."""
    result = draft_section("scope", ["Requirement A", "Requirement B"], "proj-1")
    assert "Requirement A" in result.content_markdown


def test_anthropic_draft_includes_feedback_in_stub():
    """Stub output should mention review feedback when provided."""
    result = draft_section("approach", ["Evidence"], "proj-1", review_feedback="Need more detail")
    assert "revision" in result.content_markdown.lower() or "Need more detail" in result.content_markdown


def test_anthropic_draft_calls_api_with_key():
    """With ANTHROPIC_API_KEY set, should call the Anthropic API."""
    with patch("httpx.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "## Intro\n\nDrafted content."}],
            "model": "claude-sonnet-4-20250514",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 50, "output_tokens": 20},
        }
        mock_post.return_value = mock_response

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            result = draft_section("intro", ["Evidence"], "proj-1")

        assert result.content_markdown is not None
        assert "Drafted content" in result.content_markdown
        assert "claude" in result.model_used.lower()

        # Verify correct Anthropic API format
        call_kwargs = mock_post.call_args.kwargs
        assert "x-api-key" in call_kwargs["headers"]
        assert call_kwargs["headers"]["x-api-key"] == "sk-ant-test"
        assert "anthropic-version" in call_kwargs["headers"]

        # Verify messages format (no system role in messages)
        body = call_kwargs["json"]
        assert "system" in body  # Top-level system field
        assert body["messages"][0]["role"] == "user"
        assert "max_tokens" in body
