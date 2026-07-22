from app.retrieval.reranker import rerank_candidates
from contracts import RerankOutcomeStatus
from contracts.retrieval_repository import RankedKnowledgeChunk


def _candidate(chunk_id: str, content: str) -> RankedKnowledgeChunk:
    return RankedKnowledgeChunk(
        chunk_id=chunk_id,
        project_id="project-1",
        source_document_id="source-1",
        chunk_index=0,
        content=content,
        metadata_json={},
        score=0.1,
        method="dense",
    )


def _clear_rerank_env(monkeypatch) -> None:
    for name in ("DOCPILOT_RERANK_API_KEY", "DOCPILOT_RERANK_API_URL", "DOCPILOT_RERANK_MODEL"):
        monkeypatch.delenv(name, raising=False)


def test_reranker_is_disabled_without_complete_explicit_configuration(monkeypatch) -> None:
    _clear_rerank_env(monkeypatch)

    outcome = rerank_candidates("云平台部署", [_candidate("chunk-1", "云平台部署方案")], top_k=1)

    assert outcome.status is RerankOutcomeStatus.DISABLED
    assert outcome.scores == {}


def test_reranker_maps_provider_indexes_back_to_chunk_ids(monkeypatch) -> None:
    _clear_rerank_env(monkeypatch)
    monkeypatch.setenv("DOCPILOT_RERANK_API_KEY", "test-key")
    monkeypatch.setenv("DOCPILOT_RERANK_API_URL", "https://example.test/rerank")
    monkeypatch.setenv("DOCPILOT_RERANK_MODEL", "qwen/qwen3-reranker-8b")

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "results": [
                    {"index": 1, "relevance_score": 0.98},
                    {"index": 0, "relevance_score": 0.25},
                ]
            }

    monkeypatch.setattr("app.retrieval.reranker.httpx.post", lambda *_args, **_kwargs: Response())

    outcome = rerank_candidates(
        "云平台部署",
        [
            _candidate("chunk-1", "无关内容"),
            _candidate("chunk-2", "云平台部署方案"),
        ],
        top_k=2,
    )

    assert outcome.status is RerankOutcomeStatus.SUCCESS
    assert outcome.scores == {"chunk-2": 0.98, "chunk-1": 0.25}


def test_reranker_timeout_is_explicit_and_does_not_return_partial_scores(monkeypatch) -> None:
    _clear_rerank_env(monkeypatch)
    monkeypatch.setenv("DOCPILOT_RERANK_API_KEY", "test-key")
    monkeypatch.setenv("DOCPILOT_RERANK_API_URL", "https://example.test/rerank")
    monkeypatch.setenv("DOCPILOT_RERANK_MODEL", "qwen/qwen3-reranker-8b")

    def raise_timeout(*_args, **_kwargs):
        from app.retrieval import reranker

        raise reranker.httpx.TimeoutException("simulated timeout")

    monkeypatch.setattr("app.retrieval.reranker.httpx.post", raise_timeout)

    outcome = rerank_candidates("云平台部署", [_candidate("chunk-1", "云平台部署方案")], top_k=1)

    assert outcome.status is RerankOutcomeStatus.TRANSIENT_FAILURE
    assert outcome.scores == {}
    assert outcome.error_code == "reranker_timeout"
