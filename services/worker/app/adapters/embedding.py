"""Embedding adapter for chunk vectorization.

Calls an OpenAI-compatible embeddings API. Falls back to a zero-vector
stub when no API key is configured.
"""

import logging
import os
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 1536
_DEFAULT_URL = "https://api.openai.com/v1/embeddings"
_DEFAULT_MODEL = "text-embedding-3-small"


@dataclass
class EmbeddingResult:
    embedding: list[float]
    model: str
    token_count: int = 0


def _api_key() -> str | None:
    return os.environ.get("EMBEDDING_API_KEY") or os.environ.get("OPENAI_API_KEY")


def _api_url() -> str:
    return os.environ.get("EMBEDDING_API_URL", _DEFAULT_URL)


def _api_model() -> str:
    return os.environ.get("EMBEDDING_MODEL", _DEFAULT_MODEL)


def generate_embedding(text: str) -> EmbeddingResult:
    """Generate an embedding vector for the given text.

    If no API key is configured, returns a zero-vector stub.
    """
    api_key = _api_key()
    if not api_key:
        logger.debug("No embedding API key configured, returning zero-vector stub")
        return EmbeddingResult(
            embedding=[0.0] * EMBEDDING_DIM,
            model="stub",
            token_count=0,
        )

    url = _api_url()
    model = _api_model()

    try:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"input": text, "model": model},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        embedding = data["data"][0]["embedding"]
        usage = data.get("usage", {})
        return EmbeddingResult(
            embedding=embedding,
            model=model,
            token_count=usage.get("total_tokens", 0),
        )
    except Exception as exc:
        logger.warning("Embedding API call failed: %s", exc)
        return EmbeddingResult(
            embedding=[0.0] * EMBEDDING_DIM,
            model="fallback",
            token_count=0,
        )


def generate_embeddings_batch(texts: list[str]) -> list[EmbeddingResult]:
    """Generate embeddings for a batch of texts.

    Falls back to per-text generation if batch endpoint is unavailable.
    """
    api_key = _api_key()
    if not api_key:
        return [generate_embedding(t) for t in texts]

    url = _api_url()
    model = _api_model()

    try:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"input": texts, "model": model},
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()
        results: list[EmbeddingResult] = []
        for item in data["data"]:
            results.append(EmbeddingResult(
                embedding=item["embedding"],
                model=model,
                token_count=data.get("usage", {}).get("total_tokens", 0),
            ))
        return results
    except Exception as exc:
        logger.warning("Batch embedding failed, falling back to per-text: %s", exc)
        return [generate_embedding(t) for t in texts]
