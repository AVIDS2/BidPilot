"""Shared PostgreSQL candidate queries for BidPilot Retrieval 2."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import case, func, literal_column, or_, select
from sqlalchemy.orm import Session

from .models import KnowledgeChunk


_TEXT_CONFIG = literal_column("'simple'::regconfig")
_MAX_FTS_OR_TERMS = 64


@dataclass(frozen=True, slots=True)
class RankedKnowledgeChunk:
    chunk_id: str
    project_id: str
    source_document_id: str
    chunk_index: int
    content: str
    metadata_json: dict | None
    score: float
    method: Literal["dense", "fts", "trigram"]


def _limit(top_k: int) -> int:
    if top_k < 1:
        raise ValueError("top_k must be positive")
    return top_k


def supports_postgresql_retrieval(db: Session) -> bool:
    """Return whether this session can use the PostgreSQL retrieval operators."""
    return db.get_bind().dialect.name == "postgresql"


def _record(chunk: KnowledgeChunk, *, score: float, method: Literal["dense", "fts", "trigram"]) -> RankedKnowledgeChunk:
    return RankedKnowledgeChunk(
        chunk_id=chunk.id,
        project_id=chunk.project_id,
        source_document_id=chunk.source_document_id,
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        metadata_json=chunk.metadata_json,
        score=float(score),
        method=method,
    )


def search_dense_candidates(
    db: Session,
    *,
    project_id: str,
    profile_id: str,
    query_embedding: list[float],
    top_k: int,
) -> list[RankedKnowledgeChunk]:
    """Run exact, profile-safe cosine search within one project scope."""
    if not query_embedding:
        return []
    distance = KnowledgeChunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(KnowledgeChunk, distance.label("distance"))
        .where(
            KnowledgeChunk.project_id == project_id,
            KnowledgeChunk.embedding_profile == profile_id,
            KnowledgeChunk.embedding.isnot(None),
        )
        .order_by(distance.asc(), KnowledgeChunk.id.asc())
        .limit(_limit(top_k))
    )
    return [
        _record(chunk, score=1.0 - float(distance_value), method="dense")
        for chunk, distance_value in db.execute(stmt).all()
    ]


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _portable_query_terms(*, raw_query: str, normalized_query: str) -> list[str]:
    values = [raw_query.strip(), normalized_query.strip(), *normalized_query.split()]
    return list(dict.fromkeys(value.casefold() for value in values if value.strip()))[:_MAX_FTS_OR_TERMS]


def search_portable_lexical_candidates(
    db: Session,
    *,
    project_id: str,
    raw_query: str,
    normalized_query: str,
    top_k: int,
) -> list[RankedKnowledgeChunk]:
    """Use bounded phrase/token matching when PostgreSQL operators are unavailable.

    This path is deliberately limited to non-PostgreSQL development and test
    databases. Production retrieval still requires PostgreSQL FTS, pg_trgm,
    and pgvector; callers must surface the accompanying degradation reason.
    """
    terms = _portable_query_terms(raw_query=raw_query, normalized_query=normalized_query)
    if not terms:
        return []

    def text_match(term: str):
        pattern = f"%{_escape_like(term)}%"
        return or_(
            func.lower(KnowledgeChunk.content).like(pattern, escape="\\"),
            func.lower(KnowledgeChunk.retrieval_text).like(pattern, escape="\\"),
        )

    phrase_terms = list(dict.fromkeys(value.casefold() for value in (raw_query, normalized_query) if value.strip()))
    phrase_match = or_(*(text_match(term) for term in phrase_terms))
    token_matches = [text_match(term) for term in terms]
    score = case((phrase_match, 2.0), else_=0.0)
    for token_match in token_matches:
        score = score + case((token_match, 1.0), else_=0.0)

    stmt = (
        select(KnowledgeChunk, score.label("score"))
        .where(
            KnowledgeChunk.project_id == project_id,
            or_(*token_matches),
        )
        .order_by(score.desc(), KnowledgeChunk.id.asc())
        .limit(_limit(top_k))
    )
    return [
        _record(chunk, score=float(score_value), method="fts")
        for chunk, score_value in db.execute(stmt).all()
    ]


def search_fts_candidates(
    db: Session,
    *,
    project_id: str,
    normalized_query: str,
    top_k: int,
) -> list[RankedKnowledgeChunk]:
    """Retrieve lexical candidates through the indexed normalized search text."""
    if not normalized_query.strip():
        return []
    search_vector = func.to_tsvector(_TEXT_CONFIG, KnowledgeChunk.retrieval_text)
    search_query = func.websearch_to_tsquery(_TEXT_CONFIG, normalized_query)
    strict_results = _run_fts_query(
        db,
        project_id=project_id,
        search_vector=search_vector,
        search_query=search_query,
        top_k=top_k,
    )
    if strict_results:
        return strict_results

    # CJK bigrams intentionally do not all occur in any one chunk for a
    # multi-concept question. A bounded OR retry preserves lexical scope while
    # avoiding the false-negative behaviour of strict AND matching.
    fallback_text = _or_query_text(normalized_query)
    if not fallback_text:
        return []
    fallback_query = func.websearch_to_tsquery(_TEXT_CONFIG, fallback_text)
    return _run_fts_query(
        db,
        project_id=project_id,
        search_vector=search_vector,
        search_query=fallback_query,
        top_k=top_k,
    )


def _run_fts_query(
    db: Session,
    *,
    project_id: str,
    search_vector,
    search_query,
    top_k: int,
) -> list[RankedKnowledgeChunk]:
    rank = func.ts_rank_cd(search_vector, search_query, 32)
    stmt = (
        select(KnowledgeChunk, rank.label("score"))
        .where(
            KnowledgeChunk.project_id == project_id,
            search_vector.op("@@")(search_query),
        )
        .order_by(rank.desc(), KnowledgeChunk.id.asc())
        .limit(_limit(top_k))
    )
    return [
        _record(chunk, score=float(score), method="fts")
        for chunk, score in db.execute(stmt).all()
    ]


def _or_query_text(normalized_query: str) -> str:
    terms = list(dict.fromkeys(normalized_query.split()))[:_MAX_FTS_OR_TERMS]
    # Quotes make websearch_to_tsquery treat every normalized term as data,
    # not as an operator supplied by the user.
    return " OR ".join(f'"{term}"' for term in terms if term)


def _trigram_terms(raw_query: str) -> list[str]:
    """Split multi-keyword queries into phrase-sized terms for CJK recall.

    Full-query similarity against a long bilingual string is near zero for
    Chinese corpora. Individual 2+ character terms (技术方案, 微服务) remain
    high-signal for ``ilike`` / ``%`` matching.
    """
    query = raw_query.strip()
    if not query:
        return []
    terms: list[str] = []
    # Prefer whitespace-delimited keywords first (section expansion path).
    for part in re.split(r"\s+", query):
        token = part.strip()
        if len(token) >= 2:
            terms.append(token)
    # Also keep the full query for exact phrase hits on short inputs.
    if query not in terms and len(query) >= 2:
        terms.insert(0, query)
    # Deduplicate while preserving order; cap to keep the OR clause bounded.
    ordered: list[str] = []
    seen: set[str] = set()
    for term in terms:
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(term)
        if len(ordered) >= 16:
            break
    return ordered


def search_trigram_candidates(
    db: Session,
    *,
    project_id: str,
    raw_query: str,
    top_k: int,
) -> list[RankedKnowledgeChunk]:
    """Retrieve exact phrases and typo-tolerant candidates for legacy/CJK content."""
    terms = _trigram_terms(raw_query)
    if not terms:
        return []

    # Score = sum of per-term phrase hits + best single-term similarity.
    # This recovers Chinese section-key expansions where the full bilingual
    # string would never substring-match a knowledge chunk.
    phrase_matches = [
        KnowledgeChunk.content.ilike(f"%{_escape_like(term)}%", escape="\\")
        for term in terms
    ]
    phrase_score = case((phrase_matches[0], 1.0), else_=0.0)
    for match in phrase_matches[1:]:
        phrase_score = phrase_score + case((match, 1.0), else_=0.0)

    similarity = func.greatest(
        *[func.similarity(KnowledgeChunk.content, term) for term in terms]
    )
    similarity_matches = [KnowledgeChunk.content.op("%")(term) for term in terms]
    stmt = (
        select(KnowledgeChunk, (phrase_score + similarity).label("score"))
        .where(
            KnowledgeChunk.project_id == project_id,
            or_(*phrase_matches, *similarity_matches),
        )
        .order_by(phrase_score.desc(), similarity.desc(), KnowledgeChunk.id.asc())
        .limit(_limit(top_k))
    )
    return [
        _record(chunk, score=float(score), method="trigram")
        for chunk, score in db.execute(stmt).all()
    ]


__all__ = [
    "RankedKnowledgeChunk",
    "supports_postgresql_retrieval",
    "search_dense_candidates",
    "search_portable_lexical_candidates",
    "search_fts_candidates",
    "search_trigram_candidates",
]
