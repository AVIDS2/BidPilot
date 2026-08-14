"""Shared hybrid retrieval service over the BidPilot PostgreSQL repositories."""

from __future__ import annotations

import time
import unicodedata
from collections.abc import Iterable
from typing import Callable

from sqlalchemy.orm import Session

from .retrieval import (
    CitationLocator,
    CitationValidationStatus,
    RerankOutcome,
    RerankOutcomeStatus,
    RetrievalCandidate,
    RetrievalResult,
    RetrievalTrace,
    normalize_retrieval_text,
    reciprocal_rank_fusion,
)
from .retrieval_repository import (
    RankedKnowledgeChunk,
    search_dense_candidates,
    search_fts_candidates,
    search_trigram_candidates,
    supports_postgresql_retrieval,
)


_METHOD_ORDER = ("dense", "fts", "trigram")
Reranker = Callable[[str, list[RankedKnowledgeChunk], int], RerankOutcome]


def _normalized_anchor(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).casefold().split())


def _string_metadata(metadata: dict | None, key: str) -> str | None:
    if not metadata:
        return None
    value = metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _heading_metadata(metadata: dict | None) -> str | None:
    if not metadata:
        return None
    value = metadata.get("heading_path")
    if not isinstance(value, list):
        return None
    headings = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return " / ".join(headings)[:1000] or None


def _table_metadata(metadata: dict | None) -> str | None:
    if not metadata:
        return None
    headers = metadata.get("table_headers")
    if not isinstance(headers, list):
        return None
    values = [item.strip() for item in headers if isinstance(item, str) and item.strip()]
    return " | ".join(values)[:1000] or None


def build_citation_locator(chunk: RankedKnowledgeChunk) -> CitationLocator:
    """Construct and validate a source locator from persisted chunk provenance."""
    metadata = chunk.metadata_json or {}
    metadata_source = _string_metadata(metadata, "source_document_id")
    heading = _heading_metadata(metadata)
    table = _table_metadata(metadata)
    page_value = metadata.get("page") if isinstance(metadata, dict) else None
    page = page_value if isinstance(page_value, int) and page_value > 0 else None
    anchor = _string_metadata(metadata, "text_anchor") or chunk.content[:240].strip() or None

    if metadata_source is not None and metadata_source != chunk.source_document_id:
        return CitationLocator(
            source_document_id=chunk.source_document_id,
            chunk_index=chunk.chunk_index,
            page=page,
            heading=heading,
            table=table,
            text_anchor=anchor,
            validation_status=CitationValidationStatus.INVALID,
            validation_reason="metadata_source_mismatch",
        )

    if anchor and _normalized_anchor(anchor) not in _normalized_anchor(chunk.content):
        return CitationLocator(
            source_document_id=chunk.source_document_id,
            chunk_index=chunk.chunk_index,
            page=page,
            heading=heading,
            table=table,
            text_anchor=anchor,
            validation_status=CitationValidationStatus.INVALID,
            validation_reason="text_anchor_not_found",
        )

    return CitationLocator(
        source_document_id=chunk.source_document_id,
        chunk_index=chunk.chunk_index,
        page=page,
        heading=heading,
        table=table,
        text_anchor=anchor,
        validation_status=(
            CitationValidationStatus.VERIFIED
            if any((page, heading, table))
            else CitationValidationStatus.PARTIAL
        ),
        validation_reason=None if any((page, heading, table)) else "chunk_anchor_only",
    )


def _add_ranked_records(
    rankings: dict[str, list[str]],
    records: dict[str, RankedKnowledgeChunk],
    method: str,
    candidates: Iterable[RankedKnowledgeChunk],
) -> None:
    method_candidates = list(candidates)
    rankings[method] = [candidate.chunk_id for candidate in method_candidates]
    for candidate in method_candidates:
        records.setdefault(candidate.chunk_id, candidate)


def retrieve_project_evidence(
    db: Session,
    *,
    project_id: str,
    raw_query: str,
    profile_id: str | None,
    query_embedding: list[float] | None,
    top_k: int,
    reranker: Reranker | None = None,
) -> RetrievalResult:
    """Retrieve project evidence with dense, FTS, trigram, and deterministic RRF."""
    if top_k < 1:
        raise ValueError("top_k must be positive")

    started = time.monotonic()
    normalized_query = normalize_retrieval_text(raw_query)
    candidate_limit = max(top_k * 4, 20)
    rankings: dict[str, list[str]] = {}
    records: dict[str, RankedKnowledgeChunk] = {}
    degraded_reasons: list[str] = []

    dense_candidates: list[RankedKnowledgeChunk] = []
    fts_candidates: list[RankedKnowledgeChunk] = []
    trigram_candidates: list[RankedKnowledgeChunk] = []
    if supports_postgresql_retrieval(db):
        if profile_id and query_embedding:
            dense_candidates = search_dense_candidates(
                db,
                project_id=project_id,
                profile_id=profile_id,
                query_embedding=query_embedding,
                top_k=candidate_limit,
            )
            _add_ranked_records(rankings, records, "dense", dense_candidates)
        else:
            degraded_reasons.append("dense_unavailable")

        fts_candidates = search_fts_candidates(
            db,
            project_id=project_id,
            normalized_query=normalized_query,
            top_k=candidate_limit,
        )
        _add_ranked_records(rankings, records, "fts", fts_candidates)

        trigram_candidates = search_trigram_candidates(
            db,
            project_id=project_id,
            raw_query=raw_query,
            top_k=candidate_limit,
        )
        _add_ranked_records(rankings, records, "trigram", trigram_candidates)
    else:
        # Test/dev backends do not implement PostgreSQL operators. The shared
        # repositories provide bounded local adapters so contract tests still
        # exercise dense/sparse fusion and citation behavior.
        degraded_reasons.append("postgresql_retrieval_unavailable")
        if profile_id and query_embedding:
            dense_candidates = search_dense_candidates(
                db,
                project_id=project_id,
                profile_id=profile_id,
                query_embedding=query_embedding,
                top_k=candidate_limit,
            )
        else:
            degraded_reasons.append("dense_unavailable")
        _add_ranked_records(rankings, records, "dense", dense_candidates)

        fts_candidates = search_fts_candidates(
            db,
            project_id=project_id,
            normalized_query=normalized_query,
            top_k=candidate_limit,
        )
        _add_ranked_records(rankings, records, "fts", fts_candidates)

        trigram_candidates = search_trigram_candidates(
            db,
            project_id=project_id,
            raw_query=raw_query,
            top_k=candidate_limit,
        )
        _add_ranked_records(rankings, records, "trigram", trigram_candidates)

    fused_candidates = list(reciprocal_rank_fusion(rankings))
    rrf_ranks = {
        fused.chunk_id: index
        for index, fused in enumerate(fused_candidates, start=1)
    }
    rerank_scores: dict[str, float] = {}
    reranked_candidate_count = 0
    if reranker is not None and fused_candidates:
        try:
            outcome = reranker(
                raw_query,
                [records[fused.chunk_id] for fused in fused_candidates],
                top_k,
            )
        except Exception:
            degraded_reasons.append("reranker_unavailable")
        else:
            if outcome.status is RerankOutcomeStatus.SUCCESS:
                rerank_scores = {
                    chunk_id: score
                    for chunk_id, score in outcome.scores.items()
                    if chunk_id in records
                }
                reranked_candidate_count = len(rerank_scores)
                if rerank_scores:
                    fused_candidates.sort(
                        key=lambda fused: (
                            -rerank_scores.get(fused.chunk_id, float("-inf")),
                            -fused.score,
                            fused.chunk_id,
                        )
                    )
            elif outcome.status is not RerankOutcomeStatus.DISABLED:
                degraded_reasons.append(outcome.error_code or "reranker_unavailable")

    candidates: list[RetrievalCandidate] = []
    invalid_locator_count = 0
    for fused in fused_candidates:
        if len(candidates) >= top_k:
            break
        record = records[fused.chunk_id]
        locator = build_citation_locator(record)
        if locator.validation_status is CitationValidationStatus.INVALID:
            invalid_locator_count += 1
            continue
        rerank_score = rerank_scores.get(fused.chunk_id)
        methods = tuple(method for method in _METHOD_ORDER if method in fused.method_ranks)
        if rerank_score is not None:
            methods = (*methods, "rerank")
        sparse_ranks = [
            fused.method_ranks[method]
            for method in ("fts", "trigram")
            if method in fused.method_ranks
        ]
        candidates.append(
            RetrievalCandidate(
                chunk_id=record.chunk_id,
                project_id=record.project_id,
                source_document_id=record.source_document_id,
                content=record.content,
                locator=locator,
                dense_rank=fused.method_ranks.get("dense"),
                sparse_rank=min(sparse_ranks) if sparse_ranks else None,
                fused_rank=rrf_ranks[fused.chunk_id],
                rerank_score=rerank_score,
                final_score=rerank_score if rerank_score is not None else fused.score,
                methods=methods,
            )
        )

    if invalid_locator_count:
        degraded_reasons.append("invalid_citation_locator")
    if not candidates:
        degraded_reasons.append("no_evidence_found")

    trace = RetrievalTrace(
        profile_id=profile_id,
        query_kind="project_evidence",
        dense_candidate_count=len(dense_candidates),
        fts_candidate_count=len(fts_candidates),
        trigram_candidate_count=len(trigram_candidates),
        fused_candidate_count=len(records),
        reranked_candidate_count=reranked_candidate_count,
        returned_candidate_count=len(candidates),
        degraded_reasons=tuple(degraded_reasons),
        latency_ms=int((time.monotonic() - started) * 1000),
    )
    return RetrievalResult(
        project_id=project_id,
        profile_id=profile_id,
        candidates=tuple(candidates),
        degraded_reasons=tuple(degraded_reasons),
        trace=trace,
    )


__all__ = ["build_citation_locator", "retrieve_project_evidence"]
