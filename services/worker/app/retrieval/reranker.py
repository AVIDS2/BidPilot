"""Optional server-configured HTTP reranker for the bounded fused candidate set."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx

from contracts import RerankOutcome, RerankOutcomeStatus
from contracts.retrieval_repository import RankedKnowledgeChunk


@dataclass(frozen=True)
class _RerankerConfig:
    api_key: str = field(repr=False)
    api_url: str
    model: str


def _config() -> _RerankerConfig | None:
    api_key = os.getenv("DOCPILOT_RERANK_API_KEY")
    api_url = os.getenv("DOCPILOT_RERANK_API_URL")
    model = os.getenv("DOCPILOT_RERANK_MODEL")
    if not api_key or not api_url or not model:
        return None
    return _RerankerConfig(api_key=api_key, api_url=api_url, model=model)


def _failure(status: RerankOutcomeStatus, error_code: str) -> RerankOutcome:
    return RerankOutcome(status=status, error_code=error_code)


def _parse_scores(payload: Any, candidates: list[RankedKnowledgeChunk]) -> dict[str, float]:
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise ValueError("invalid_reranker_response")

    scores: dict[str, float] = {}
    for item in payload["results"]:
        if not isinstance(item, dict):
            raise ValueError("invalid_reranker_response")
        index = item.get("index")
        score = item.get("relevance_score", item.get("relevanceScore"))
        if isinstance(index, bool) or not isinstance(index, int) or index < 0 or index >= len(candidates):
            raise ValueError("invalid_reranker_response")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValueError("invalid_reranker_response")
        scores[candidates[index].chunk_id] = float(score)
    if not scores:
        raise ValueError("invalid_reranker_response")
    return scores


def rerank_candidates(
    query: str,
    candidates: list[RankedKnowledgeChunk],
    *,
    top_k: int,
) -> RerankOutcome:
    """Rerank a bounded list only when all server-side settings are explicit."""
    if top_k < 1:
        raise ValueError("top_k must be positive")
    config = _config()
    if config is None or not candidates:
        return RerankOutcome(status=RerankOutcomeStatus.DISABLED)

    try:
        response = httpx.post(
            config.api_url,
            headers={"Authorization": f"Bearer {config.api_key}"},
            json={
                "model": config.model,
                "query": query,
                "documents": [candidate.content for candidate in candidates],
                "top_n": min(top_k, len(candidates)),
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return RerankOutcome(
            status=RerankOutcomeStatus.SUCCESS,
            scores=_parse_scores(response.json(), candidates),
        )
    except httpx.TimeoutException:
        return _failure(RerankOutcomeStatus.TRANSIENT_FAILURE, "reranker_timeout")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {408, 409, 425, 429} or exc.response.status_code >= 500:
            return _failure(RerankOutcomeStatus.TRANSIENT_FAILURE, "reranker_unavailable")
        return _failure(RerankOutcomeStatus.PERMANENT_FAILURE, "reranker_rejected_request")
    except httpx.RequestError:
        return _failure(RerankOutcomeStatus.TRANSIENT_FAILURE, "reranker_unavailable")
    except (TypeError, ValueError):
        return _failure(RerankOutcomeStatus.PERMANENT_FAILURE, "invalid_reranker_response")


__all__ = ["rerank_candidates"]
