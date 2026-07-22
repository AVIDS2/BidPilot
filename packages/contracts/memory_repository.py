"""Scoped PostgreSQL candidate queries for governed Agent memory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import case, false, func, literal_column, or_, select
from sqlalchemy.orm import Session, selectinload

from .models import MemoryRecord


_TEXT_CONFIG = literal_column("'simple'::regconfig")
_MAX_FTS_OR_TERMS = 64


@dataclass(frozen=True, slots=True)
class RankedMemoryRecord:
    record: MemoryRecord
    score: float
    method: Literal["dense", "fts", "trigram"]

    @property
    def record_id(self) -> str:
        return self.record.id


def _limit(top_k: int) -> int:
    if top_k < 1:
        raise ValueError("top_k must be positive")
    return top_k


def _visible_memory_filters(
    *,
    org_id: str,
    user_id: str,
    project_id: str | None,
    now: datetime,
) -> tuple:
    """Apply tenancy and visibility constraints before every retrieval query."""
    private_scope = (MemoryRecord.scope == "user_private") & (MemoryRecord.owner_user_id == user_id)
    if project_id is None:
        visible_scope = private_scope & MemoryRecord.project_id.is_(None)
    else:
        project_scope = (MemoryRecord.scope == "project_shared") & (MemoryRecord.project_id == project_id)
        private_scope = private_scope & (
            (MemoryRecord.project_id == project_id) | MemoryRecord.project_id.is_(None)
        )
        visible_scope = project_scope | private_scope

    return (
        MemoryRecord.org_id == org_id,
        MemoryRecord.status == "active",
        MemoryRecord.deleted_at.is_(None),
        or_(MemoryRecord.expires_at.is_(None), MemoryRecord.expires_at > now),
        visible_scope if visible_scope is not None else false(),
    )


def _base_statement(*, org_id: str, user_id: str, project_id: str | None, now: datetime):
    return (
        select(MemoryRecord)
        .options(selectinload(MemoryRecord.evidence_links))
        .where(*_visible_memory_filters(org_id=org_id, user_id=user_id, project_id=project_id, now=now))
    )


def has_visible_memory(
    db: Session,
    *,
    org_id: str,
    user_id: str,
    project_id: str | None,
    now: datetime,
) -> bool:
    """Check visibility before paying the latency cost of semantic recall."""
    stmt = select(MemoryRecord.id).where(
        *_visible_memory_filters(
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            now=now,
        )
    ).limit(1)
    return db.scalar(stmt) is not None


def search_dense_memory_candidates(
    db: Session,
    *,
    org_id: str,
    user_id: str,
    project_id: str | None,
    profile_id: str,
    query_embedding: list[float],
    now: datetime,
    top_k: int,
) -> list[RankedMemoryRecord]:
    """Run exact-profile dense recall only after scope filtering."""
    if not query_embedding:
        return []
    distance = MemoryRecord.embedding.cosine_distance(query_embedding)
    stmt = (
        _base_statement(org_id=org_id, user_id=user_id, project_id=project_id, now=now)
        .add_columns(distance.label("distance"))
        .where(
            MemoryRecord.embedding_profile == profile_id,
            MemoryRecord.embedding.isnot(None),
        )
        .order_by(distance.asc(), MemoryRecord.id.asc())
        .limit(_limit(top_k))
    )
    return [
        RankedMemoryRecord(record=record, score=1.0 - float(distance_value), method="dense")
        for record, distance_value in db.execute(stmt).all()
    ]


def search_fts_memory_candidates(
    db: Session,
    *,
    org_id: str,
    user_id: str,
    project_id: str | None,
    normalized_query: str,
    now: datetime,
    top_k: int,
) -> list[RankedMemoryRecord]:
    """Retrieve lexical memory candidates with a bounded CJK-aware OR fallback."""
    if not normalized_query.strip():
        return []
    search_vector = func.to_tsvector(_TEXT_CONFIG, MemoryRecord.retrieval_text)
    strict_query = func.websearch_to_tsquery(_TEXT_CONFIG, normalized_query)
    strict_results = _run_fts_query(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=project_id,
        now=now,
        search_vector=search_vector,
        search_query=strict_query,
        top_k=top_k,
    )
    if strict_results:
        return strict_results

    fallback_text = _or_query_text(normalized_query)
    if not fallback_text:
        return []
    return _run_fts_query(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=project_id,
        now=now,
        search_vector=search_vector,
        search_query=func.websearch_to_tsquery(_TEXT_CONFIG, fallback_text),
        top_k=top_k,
    )


def _run_fts_query(
    db: Session,
    *,
    org_id: str,
    user_id: str,
    project_id: str | None,
    now: datetime,
    search_vector,
    search_query,
    top_k: int,
) -> list[RankedMemoryRecord]:
    rank = func.ts_rank_cd(search_vector, search_query, 32)
    stmt = (
        _base_statement(org_id=org_id, user_id=user_id, project_id=project_id, now=now)
        .add_columns(rank.label("score"))
        .where(search_vector.op("@@")(search_query))
        .order_by(rank.desc(), MemoryRecord.id.asc())
        .limit(_limit(top_k))
    )
    return [
        RankedMemoryRecord(record=record, score=float(score), method="fts")
        for record, score in db.execute(stmt).all()
    ]


def _or_query_text(normalized_query: str) -> str:
    terms = list(dict.fromkeys(normalized_query.split()))[:_MAX_FTS_OR_TERMS]
    return " OR ".join(f'"{term}"' for term in terms if term)


def search_trigram_memory_candidates(
    db: Session,
    *,
    org_id: str,
    user_id: str,
    project_id: str | None,
    raw_query: str,
    now: datetime,
    top_k: int,
) -> list[RankedMemoryRecord]:
    """Recall exact phrases and typo-tolerant memory without weakening scope filters."""
    query = raw_query.strip()
    if not query:
        return []
    phrase_match = MemoryRecord.body_markdown.ilike(f"%{query}%")
    similarity = func.similarity(MemoryRecord.body_markdown, query)
    phrase_boost = case((phrase_match, 1.0), else_=0.0)
    stmt = (
        _base_statement(org_id=org_id, user_id=user_id, project_id=project_id, now=now)
        .add_columns((phrase_boost + similarity).label("score"))
        .where(or_(phrase_match, MemoryRecord.body_markdown.op("%")(query)))
        .order_by(phrase_boost.desc(), similarity.desc(), MemoryRecord.id.asc())
        .limit(_limit(top_k))
    )
    return [
        RankedMemoryRecord(record=record, score=float(score), method="trigram")
        for record, score in db.execute(stmt).all()
    ]


def list_active_preference_memory(
    db: Session,
    *,
    org_id: str,
    user_id: str,
    project_id: str | None,
    now: datetime,
    top_k: int,
) -> list[MemoryRecord]:
    """Return a small always-on lane for the current user's explicit preferences."""
    stmt = (
        _base_statement(org_id=org_id, user_id=user_id, project_id=project_id, now=now)
        .where(
            MemoryRecord.scope == "user_private",
            MemoryRecord.kind == "preference",
            MemoryRecord.owner_user_id == user_id,
        )
        .order_by(MemoryRecord.updated_at.desc(), MemoryRecord.id.asc())
        .limit(_limit(top_k))
    )
    return list(db.scalars(stmt).all())


__all__ = [
    "RankedMemoryRecord",
    "has_visible_memory",
    "search_dense_memory_candidates",
    "search_fts_memory_candidates",
    "search_trigram_memory_candidates",
    "list_active_preference_memory",
]
