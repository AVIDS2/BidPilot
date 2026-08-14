"""Embedding adapter with explicit, non-polluting failure outcomes."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import Field

from app.adapters.provider_env import (
    embedding_api_key,
    embedding_api_url,
    embedding_dimensions,
    embedding_model,
    embedding_provider_family,
)
from app.retrieval.normalization import NORMALIZER_VERSION
from contracts import EmbeddingOutcome, EmbeddingOutcomeStatus, RetrievalProfile

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 1536
EMBEDDING_BATCH_SIZE = 4
_DEFAULT_URL = "https://api.openai.com/v1/embeddings"
_DEFAULT_MODEL = "text-embedding-3-small"


class EmbeddingResult(EmbeddingOutcome):
    """Adapter result retaining provider model metadata for existing callers."""

    model: str = Field(min_length=1, max_length=255)

    @property
    def embedding(self) -> list[float] | None:
        return self.vector


class _EmbeddingDimensionMismatch(ValueError):
    """Raised only while translating a provider response into the fixed vector schema."""


def _api_key() -> str | None:
    return embedding_api_key()


def _api_url() -> str:
    return embedding_api_url(_DEFAULT_URL)


def _api_model() -> str:
    return embedding_model(_DEFAULT_MODEL)


def _api_dimensions() -> int | None:
    return embedding_dimensions()


def _request_payload(input_value: str | list[str], model: str) -> dict[str, object]:
    payload: dict[str, object] = {"input": input_value, "model": model}
    dimensions = _api_dimensions()
    if dimensions:
        payload["dimensions"] = dimensions
    return payload


def get_embedding_profile() -> RetrievalProfile | None:
    """Return the active server-side profile or None when embeddings are unavailable."""
    if not _api_key():
        return None
    return RetrievalProfile(
        provider=embedding_provider_family() or "custom",
        model=_api_model(),
        dimensions=EMBEDDING_DIM,
        normalizer_version=NORMALIZER_VERSION,
    )


def _failure(
    *,
    status: EmbeddingOutcomeStatus,
    model: str,
    error_code: str,
    profile_id: str | None = None,
    token_count: int = 0,
    usage_reported: bool = False,
) -> EmbeddingResult:
    return EmbeddingResult(
        status=status,
        model=model,
        profile_id=profile_id,
        token_count=token_count,
        usage_reported=usage_reported,
        error_code=error_code,
    )


def _configured_values() -> tuple[str, str, str, RetrievalProfile] | None:
    api_key = _api_key()
    if not api_key:
        return None
    profile = get_embedding_profile()
    if profile is None:
        return None
    return api_key, _api_url(), _api_model(), profile


def _classify_http_error(exc: httpx.HTTPStatusError) -> EmbeddingOutcomeStatus:
    status_code = exc.response.status_code
    if status_code in {408, 409, 425, 429} or status_code >= 500:
        return EmbeddingOutcomeStatus.TRANSIENT_FAILURE
    return EmbeddingOutcomeStatus.PERMANENT_FAILURE


def _error_code_for_status(status: EmbeddingOutcomeStatus) -> str:
    if status is EmbeddingOutcomeStatus.TRANSIENT_FAILURE:
        return "provider_unavailable"
    if status is EmbeddingOutcomeStatus.PERMANENT_FAILURE:
        return "provider_rejected_request"
    return "invalid_provider_response"


def _vector_from_item(item: Any) -> list[float]:
    if not isinstance(item, dict) or not isinstance(item.get("embedding"), list):
        raise ValueError("provider response does not include an embedding list")
    vector = [float(value) for value in item["embedding"]]
    if len(vector) != EMBEDDING_DIM:
        raise _EmbeddingDimensionMismatch()
    return vector


def _results_from_response(
    payload: Any,
    *,
    expected_count: int,
    model: str,
    profile: RetrievalProfile,
) -> list[EmbeddingResult]:
    try:
        if not isinstance(payload, dict):
            raise ValueError("provider response must be an object")
        items = payload.get("data")
        if not isinstance(items, list) or len(items) != expected_count:
            raise ValueError("provider response item count does not match request")
    except (TypeError, ValueError):
        return [
            _failure(
                status=EmbeddingOutcomeStatus.PERMANENT_FAILURE,
                model=model,
                error_code="invalid_provider_response",
                profile_id=profile.identifier,
            )
            for _ in range(expected_count)
        ]

    usage = payload.get("usage")
    usage_reported = False
    token_count = 0
    if isinstance(usage, dict) and "total_tokens" in usage:
        try:
            token_count = int(usage["total_tokens"])
            if token_count < 0:
                raise ValueError
        except (TypeError, ValueError):
            logger.warning("Embedding provider returned invalid usage metadata")
        else:
            usage_reported = True

    results: list[EmbeddingResult] = []
    for item in items:
        try:
            vector = _vector_from_item(item)
        except _EmbeddingDimensionMismatch:
            results.append(
                _failure(
                    status=EmbeddingOutcomeStatus.DIMENSION_MISMATCH,
                    model=model,
                    error_code="embedding_dimension_mismatch",
                    profile_id=profile.identifier,
                    token_count=token_count,
                    usage_reported=usage_reported,
                )
            )
        except (TypeError, ValueError):
            results.append(
                _failure(
                    status=EmbeddingOutcomeStatus.PERMANENT_FAILURE,
                    model=model,
                    error_code="invalid_provider_response",
                    profile_id=profile.identifier,
                    token_count=token_count,
                    usage_reported=usage_reported,
                )
            )
        else:
            results.append(
                EmbeddingResult(
                    status=EmbeddingOutcomeStatus.SUCCESS,
                    model=model,
                    profile_id=profile.identifier,
                    vector=vector,
                    token_count=token_count,
                    usage_reported=usage_reported,
                )
            )
    return results


def _request_embeddings(
    input_value: str | list[str],
    *,
    expected_count: int,
) -> list[EmbeddingResult]:
    configured = _configured_values()
    if configured is None:
        return [
            _failure(
                status=EmbeddingOutcomeStatus.NOT_CONFIGURED,
                model="not_configured",
                error_code="embedding_not_configured",
            )
            for _ in range(expected_count)
        ]

    api_key, url, model, profile = configured
    try:
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json=_request_payload(input_value, model),
            # Indexing must recover quickly when a gateway is unhealthy.  A
            # bounded Celery retry handles transient outages; keeping one HTTP
            # request alive for a minute only makes the whole project appear
            # stuck to the user.
            timeout=20.0 if expected_count > 1 else 15.0,
        )
        response.raise_for_status()
        return _results_from_response(
            response.json(),
            expected_count=expected_count,
            model=model,
            profile=profile,
        )
    except httpx.TimeoutException:
        status = EmbeddingOutcomeStatus.TRANSIENT_FAILURE
        error_code = "provider_timeout"
    except httpx.HTTPStatusError as exc:
        status = _classify_http_error(exc)
        error_code = _error_code_for_status(status)
    except httpx.RequestError:
        status = EmbeddingOutcomeStatus.TRANSIENT_FAILURE
        error_code = "provider_unavailable"
    except (TypeError, ValueError):
        status = EmbeddingOutcomeStatus.PERMANENT_FAILURE
        error_code = "invalid_provider_response"

    logger.warning("Embedding provider call failed with category %s", error_code)
    return [
        _failure(
            status=status,
            model=model,
            error_code=error_code,
            profile_id=profile.identifier,
        )
        for _ in range(expected_count)
    ]


def generate_embedding(text: str) -> EmbeddingResult:
    """Generate one embedding without fabricating vectors on failure."""
    return _request_embeddings(text, expected_count=1)[0]


def generate_embeddings_batch(texts: list[str]) -> list[EmbeddingResult]:
    """Generate embeddings in bounded provider requests while preserving input order.

    A document bundle can contain dozens of long chunks.  Sending all of them
    through a gateway in one request makes a transient timeout fail the entire
    index.  Keep requests small so a later re-ingest can retry only the failed
    chunk records without fabricating vectors for the rest.
    """
    if not texts:
        return []
    results: list[EmbeddingResult] = []
    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[start : start + EMBEDDING_BATCH_SIZE]
        results.extend(_request_embeddings(batch, expected_count=len(batch)))
    return results
