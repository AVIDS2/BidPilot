import pytest

from app.retrieval import embedding as query_embedding
from contracts import EmbeddingOutcomeStatus


_EMBEDDING_ENV_NAMES = (
    "EMBEDDING_API_KEY",
    "EMBEDDING_API_URL",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIMENSIONS",
    "DOCPILOT_EMBEDDING_DIMENSIONS",
    "OPENROUTER_API_KEY",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_EMBEDDING_MODEL",
    "OPENROUTER_EMBEDDING_DIMENSIONS",
    "DOCPILOT_PROVIDER_DOMESTIC_API_KEY",
    "DOCPILOT_PROVIDER_DOMESTIC_BASE_URL",
    "DOCPILOT_EMBEDDING_MODEL_TEXT",
    "DOCPILOT_PROVIDER_OPENAI_API_KEY",
    "DOCPILOT_PROVIDER_OPENAI_BASE_URL",
    "OPENAI_API_KEY",
    "ALIYUN_API_KEY",
    "DASHSCOPE_API_KEY",
)


def _clear_embedding_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _EMBEDDING_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_query_embedding_without_platform_configuration_makes_no_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_embedding_env(monkeypatch)
    monkeypatch.setattr(
        query_embedding.httpx,
        "post",
        lambda *_args, **_kwargs: pytest.fail("unconfigured embedding must not call a provider"),
    )

    result = query_embedding.generate_query_embedding("cloud deployment")

    assert result.status is EmbeddingOutcomeStatus.NOT_CONFIGURED
    assert result.vector is None
    assert result.error_code == "embedding_not_configured"


def test_query_embedding_uses_openrouter_profile_and_dimension_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_embedding_env(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    captured: dict[str, object] = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "data": [{"embedding": [0.1] * 1536}],
                "usage": {"total_tokens": 4},
            }

    def fake_post(url: str, *, headers: dict[str, str], json: dict[str, object], timeout: float) -> Response:
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(query_embedding.httpx, "post", fake_post)

    result = query_embedding.generate_query_embedding("cloud deployment")

    assert result.status is EmbeddingOutcomeStatus.SUCCESS
    assert result.profile_id == "openrouter:qwen/qwen3-embedding-8b:1536:bidpilot-lexical-v1"
    assert len(result.vector or []) == 1536
    assert result.token_count == 4
    assert result.usage_reported is True
    assert captured["url"] == "https://openrouter.ai/api/v1/embeddings"
    assert captured["json"] == {
        "input": "cloud deployment",
        "model": "qwen/qwen3-embedding-8b",
        "dimensions": 1536,
    }


def test_query_embedding_rejects_wrong_dimension_without_returning_a_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_embedding_env(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"data": [{"embedding": [0.1] * 1024}]}

    monkeypatch.setattr(query_embedding.httpx, "post", lambda *_args, **_kwargs: Response())

    result = query_embedding.generate_query_embedding("cloud deployment")

    assert result.status is EmbeddingOutcomeStatus.DIMENSION_MISMATCH
    assert result.vector is None
    assert result.error_code == "embedding_dimension_mismatch"
    assert result.usage_reported is False
