"""Server-side query embedding adapter for project evidence retrieval."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from contracts import (
    EmbeddingOutcome,
    EmbeddingOutcomeStatus,
    NORMALIZER_VERSION,
    RetrievalProfile,
    embedding_api_key,
    embedding_api_url,
    embedding_dimensions,
    embedding_model,
    embedding_provider_family,
)


logger = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = 1536
_DEFAULT_API_URL = "https://api.openai.com/v1/embeddings"
_DEFAULT_MODEL = "text-embedding-3-small"


def _failure(
    status: EmbeddingOutcomeStatus,
    error_code: str,
    *,
    profile_id: str | None = None,
) -> EmbeddingOutcome:
    return EmbeddingOutcome(status=status, profile_id=profile_id, error_code=error_code)


def get_embedding_profile() -> RetrievalProfile | None:
    """Return the active platform-owned profile without exposing its credential."""
    if not embedding_api_key():
        return None
    return RetrievalProfile(
        provider=embedding_provider_family() or "custom",
        model=embedding_model(_DEFAULT_MODEL),
        dimensions=EMBEDDING_DIMENSIONS,
        normalizer_version=NORMALIZER_VERSION,
    )


def _request_payload(query: str, model: str) -> dict[str, object]:
    payload: dict[str, object] = {"input": query, "model": model}
    dimensions = embedding_dimensions()
    if dimensions:
        payload["dimensions"] = dimensions
    return payload


def _extract_embedding(payload: Any) -> tuple[list[float], int, bool]:
    if not isinstance(payload, dict):
        raise ValueError("invalid_provider_response")
    data = payload.get("data")
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise ValueError("invalid_provider_response")
    raw_vector = data[0].get("embedding")
    if not isinstance(raw_vector, list):
        raise ValueError("invalid_provider_response")
    vector = [float(value) for value in raw_vector]
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise ArithmeticError("embedding_dimension_mismatch")
    usage = payload.get("usage")
    if not isinstance(usage, dict) or "total_tokens" not in usage:
        return vector, 0, False
    try:
        token_count = int(usage["total_tokens"])
    except (TypeError, ValueError):
        return vector, 0, False
    if token_count < 0:
        return vector, 0, False
    return vector, token_count, True


def _http_failure(exc: httpx.HTTPStatusError) -> tuple[EmbeddingOutcomeStatus, str]:
    if exc.response.status_code in {408, 409, 425, 429} or exc.response.status_code >= 500:
        return EmbeddingOutcomeStatus.TRANSIENT_FAILURE, "provider_unavailable"
    return EmbeddingOutcomeStatus.PERMANENT_FAILURE, "provider_rejected_request"


def generate_query_embedding(query: str, *, timeout_seconds: float = 30.0) -> EmbeddingOutcome:
    """Embed one query using only the server-owned provider configuration."""
    api_key = embedding_api_key()
    profile = get_embedding_profile()
    if not api_key or profile is None:
        return _failure(EmbeddingOutcomeStatus.NOT_CONFIGURED, "embedding_not_configured")

    try:
        timeout = min(max(float(timeout_seconds), 0.1), 30.0)
        response = httpx.post(
            embedding_api_url(_DEFAULT_API_URL),
            headers={"Authorization": f"Bearer {api_key}"},
            json=_request_payload(query, profile.model),
            timeout=timeout,
        )
        response.raise_for_status()
        vector, token_count, usage_reported = _extract_embedding(response.json())
        return EmbeddingOutcome(
            status=EmbeddingOutcomeStatus.SUCCESS,
            profile_id=profile.identifier,
            vector=vector,
            token_count=token_count,
            usage_reported=usage_reported,
        )
    except httpx.TimeoutException:
        status, error_code = EmbeddingOutcomeStatus.TRANSIENT_FAILURE, "provider_timeout"
    except httpx.HTTPStatusError as exc:
        status, error_code = _http_failure(exc)
    except httpx.RequestError:
        status, error_code = EmbeddingOutcomeStatus.TRANSIENT_FAILURE, "provider_unavailable"
    except ArithmeticError:
        status, error_code = EmbeddingOutcomeStatus.DIMENSION_MISMATCH, "embedding_dimension_mismatch"
    except (TypeError, ValueError):
        status, error_code = EmbeddingOutcomeStatus.PERMANENT_FAILURE, "invalid_provider_response"

    logger.warning("Query embedding provider call failed with category %s", error_code)
    return _failure(status, error_code, profile_id=profile.identifier)


__all__ = ["generate_query_embedding", "get_embedding_profile"]
