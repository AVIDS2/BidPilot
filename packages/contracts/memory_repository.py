"""Scoped PostgreSQL candidate queries for governed Agent memory."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from typing import Literal

from sqlalchemy import case, false, func, literal_column, or_, select
from sqlalchemy.orm import Session, selectinload

from .models import (
    AuditEvent,
    Bundle,
    ChatConversation,
    ChatMessage,
    Evidence,
    KnowledgeChunk,
    MemoryEvidenceLink,
    MemoryRecord,
    RequirementItem,
    SourceDocument,
)
from .retrieval import normalize_retrieval_text


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
    include_user_private: bool = True,
) -> tuple:
    """Apply tenancy and visibility constraints before every retrieval query."""
    private_scope = (
        (MemoryRecord.scope == "user_private") & (MemoryRecord.owner_user_id == user_id)
        if include_user_private
        else false()
    )
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


def _base_statement(
    *,
    org_id: str,
    user_id: str,
    project_id: str | None,
    now: datetime,
    include_user_private: bool = True,
):
    return (
        select(MemoryRecord)
        .options(selectinload(MemoryRecord.evidence_links))
        .where(
            *_visible_memory_filters(
                org_id=org_id,
                user_id=user_id,
                project_id=project_id,
                now=now,
                include_user_private=include_user_private,
            )
        )
    )


def _uses_postgres(db: Session) -> bool:
    """Keep PostgreSQL search operators out of the SQLite unit-test adapter."""

    return db.get_bind().dialect.name == "postgresql"


def _local_candidate_limit(top_k: int) -> int:
    return max(_limit(top_k) * 8, 64)


def _search_local_lexical_candidates(
    db: Session,
    *,
    org_id: str,
    user_id: str,
    project_id: str | None,
    normalized_query: str,
    now: datetime,
    top_k: int,
    method: Literal["fts", "trigram"],
    include_user_private: bool = True,
) -> list[RankedMemoryRecord]:
    """Bounded deterministic fallback used only by non-PostgreSQL test DBs."""

    terms = tuple(dict.fromkeys(term for term in normalized_query.split() if term))
    if not terms:
        return []
    statement = (
        _base_statement(
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            now=now,
            include_user_private=include_user_private,
        )
        .order_by(MemoryRecord.updated_at.desc(), MemoryRecord.id.asc())
        .limit(_local_candidate_limit(top_k))
    )
    ranked: list[RankedMemoryRecord] = []
    for record in db.scalars(statement).all():
        text = (record.retrieval_text or "").casefold()
        matched_terms = sum(term in text for term in terms)
        if not matched_terms:
            continue
        ranked.append(
            RankedMemoryRecord(
                record=record,
                score=matched_terms / len(terms),
                method=method,
            )
        )
    return sorted(ranked, key=lambda candidate: (-candidate.score, candidate.record_id))[: _limit(top_k)]


def _search_local_dense_candidates(
    db: Session,
    *,
    org_id: str,
    user_id: str,
    project_id: str | None,
    profile_id: str,
    query_embedding: list[float],
    now: datetime,
    top_k: int,
    include_user_private: bool = True,
) -> list[RankedMemoryRecord]:
    """Small, scope-safe cosine fallback for SQLite unit tests only."""

    query_norm = sqrt(sum(value * value for value in query_embedding))
    if not query_norm:
        return []
    statement = (
        _base_statement(
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            now=now,
            include_user_private=include_user_private,
        )
        .where(
            MemoryRecord.embedding_profile == profile_id,
            MemoryRecord.embedding.isnot(None),
        )
        .order_by(MemoryRecord.id.asc())
        .limit(_local_candidate_limit(top_k))
    )
    ranked: list[RankedMemoryRecord] = []
    for record in db.scalars(statement).all():
        try:
            embedding = [float(value) for value in record.embedding]
        except (TypeError, ValueError):
            continue
        if len(embedding) != len(query_embedding):
            continue
        embedding_norm = sqrt(sum(value * value for value in embedding))
        if not embedding_norm:
            continue
        score = sum(left * right for left, right in zip(embedding, query_embedding)) / (
            embedding_norm * query_norm
        )
        ranked.append(RankedMemoryRecord(record=record, score=score, method="dense"))
    return sorted(ranked, key=lambda candidate: (-candidate.score, candidate.record_id))[: _limit(top_k)]


def has_visible_memory(
    db: Session,
    *,
    org_id: str,
    user_id: str,
    project_id: str | None,
    now: datetime,
    include_user_private: bool = True,
) -> bool:
    """Check visibility before paying the latency cost of semantic recall."""
    stmt = select(MemoryRecord.id).where(
        *_visible_memory_filters(
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            now=now,
            include_user_private=include_user_private,
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
    include_user_private: bool = True,
) -> list[RankedMemoryRecord]:
    """Run exact-profile dense recall only after scope filtering."""
    if not query_embedding:
        return []
    if not _uses_postgres(db):
        return _search_local_dense_candidates(
            db,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            profile_id=profile_id,
            query_embedding=query_embedding,
            now=now,
            top_k=top_k,
            include_user_private=include_user_private,
        )
    distance = MemoryRecord.embedding.cosine_distance(query_embedding)
    stmt = (
        _base_statement(
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            now=now,
            include_user_private=include_user_private,
        )
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
    include_user_private: bool = True,
) -> list[RankedMemoryRecord]:
    """Retrieve lexical memory candidates with a bounded CJK-aware OR fallback."""
    if not normalized_query.strip():
        return []
    if not _uses_postgres(db):
        return _search_local_lexical_candidates(
            db,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            normalized_query=normalized_query,
            now=now,
            top_k=top_k,
            method="fts",
            include_user_private=include_user_private,
        )
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
        include_user_private=include_user_private,
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
        include_user_private=include_user_private,
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
    include_user_private: bool = True,
) -> list[RankedMemoryRecord]:
    rank = func.ts_rank_cd(search_vector, search_query, 32)
    stmt = (
        _base_statement(
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            now=now,
            include_user_private=include_user_private,
        )
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
    include_user_private: bool = True,
) -> list[RankedMemoryRecord]:
    """Recall exact phrases and typo-tolerant memory without weakening scope filters."""
    query = raw_query.strip()
    if not query:
        return []
    if not _uses_postgres(db):
        return _search_local_lexical_candidates(
            db,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            normalized_query=normalize_retrieval_text(query),
            now=now,
            top_k=top_k,
            method="trigram",
            include_user_private=include_user_private,
        )
    phrase_match = MemoryRecord.body_markdown.ilike(f"%{query}%")
    similarity = func.similarity(MemoryRecord.body_markdown, query)
    phrase_boost = case((phrase_match, 1.0), else_=0.0)
    stmt = (
        _base_statement(
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            now=now,
            include_user_private=include_user_private,
        )
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
    include_user_private: bool = True,
) -> list[MemoryRecord]:
    """Return a small always-on lane for the current user's explicit preferences."""
    if not include_user_private:
        return []
    stmt = (
        _base_statement(
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            now=now,
            include_user_private=True,
        )
        .where(
            MemoryRecord.scope == "user_private",
            MemoryRecord.kind == "preference",
            MemoryRecord.owner_user_id == user_id,
        )
        .order_by(MemoryRecord.updated_at.desc(), MemoryRecord.id.asc())
        .limit(_limit(top_k))
    )
    return list(db.scalars(stmt).all())


def valid_memory_evidence_links(
    db: Session,
    *,
    records: Iterable[MemoryRecord],
) -> dict[str, tuple[MemoryEvidenceLink, ...]]:
    """Return only citations whose backing source is still usable and in scope.

    Memory records are immutable ledger entries, but their source rows can be
    removed or become unavailable later. Retrieval must therefore revalidate
    evidence instead of trusting the link that was checked at proposal time.
    Source-document supersession is intentionally not invalidation: the cited
    document version remains an auditable historical source until it is no
    longer parseable or addressable.
    """

    records_by_id = {record.id: record for record in records}
    links = [link for record in records_by_id.values() for link in record.evidence_links]
    if not links:
        return {}

    source_ids: dict[str, set[str]] = defaultdict(set)
    for link in links:
        source_ids[link.source_type].add(link.source_id)

    chunk_projects = _knowledge_chunk_projects(db, source_ids.get("knowledge_chunk", set()))
    requirement_projects = _requirement_projects(db, source_ids.get("requirement_item", set()))
    evidence_projects = _evidence_projects(db, source_ids.get("evidence_item", set()))
    chat_sources = _chat_message_sources(db, source_ids.get("chat_message", set()))
    audit_projects = _audit_event_projects(db, source_ids.get("audit_event", set()))

    valid_by_record: dict[str, list[MemoryEvidenceLink]] = defaultdict(list)
    for link in links:
        record = records_by_id[link.memory_record_id]
        if _is_valid_memory_evidence_link(
            link=link,
            record=record,
            chunk_projects=chunk_projects,
            requirement_projects=requirement_projects,
            evidence_projects=evidence_projects,
            chat_sources=chat_sources,
            audit_projects=audit_projects,
        ):
            valid_by_record[record.id].append(link)

    return {
        record_id: tuple(
            sorted(
                valid_links,
                key=lambda link: (link.source_type, link.source_id, link.evidence_role, link.id),
            )
        )
        for record_id, valid_links in valid_by_record.items()
    }


def _knowledge_chunk_projects(db: Session, source_ids: set[str]) -> dict[str, str]:
    if not source_ids:
        return {}
    rows = db.execute(
        select(KnowledgeChunk.id, KnowledgeChunk.project_id)
        .join(SourceDocument, SourceDocument.id == KnowledgeChunk.source_document_id)
        .join(Bundle, Bundle.id == SourceDocument.bundle_id)
        .where(
            KnowledgeChunk.id.in_(source_ids),
            SourceDocument.parse_status == "parsed",
            Bundle.project_id == KnowledgeChunk.project_id,
        )
    ).all()
    return {source_id: project_id for source_id, project_id in rows}


def _requirement_projects(db: Session, source_ids: set[str]) -> dict[str, str]:
    if not source_ids:
        return {}
    return dict(db.execute(select(RequirementItem.id, RequirementItem.project_id).where(RequirementItem.id.in_(source_ids))).all())


def _evidence_projects(db: Session, source_ids: set[str]) -> dict[str, str]:
    if not source_ids:
        return {}
    rows = db.execute(
        select(
            Evidence.id,
            Evidence.project_id,
            Evidence.source_document_id,
            SourceDocument.id,
            Bundle.project_id,
        )
        .outerjoin(SourceDocument, SourceDocument.id == Evidence.source_document_id)
        .outerjoin(Bundle, Bundle.id == SourceDocument.bundle_id)
        .where(Evidence.id.in_(source_ids))
    ).all()
    return {
        evidence_id: project_id
        for evidence_id, project_id, source_document_id, resolved_source_id, bundle_project_id in rows
        if source_document_id is None or (resolved_source_id is not None and bundle_project_id == project_id)
    }


def _chat_message_sources(db: Session, source_ids: set[str]) -> dict[str, tuple[str | None, str]]:
    if not source_ids:
        return {}
    rows = db.execute(
        select(ChatMessage.id, ChatConversation.project_id, ChatConversation.user_id)
        .join(ChatConversation, ChatConversation.id == ChatMessage.conversation_id)
        .where(ChatMessage.id.in_(source_ids))
    ).all()
    return {message_id: (project_id, user_id) for message_id, project_id, user_id in rows}


def _audit_event_projects(db: Session, source_ids: set[str]) -> dict[str, str]:
    if not source_ids:
        return {}
    return dict(db.execute(select(AuditEvent.id, AuditEvent.project_id).where(AuditEvent.id.in_(source_ids))).all())


def _is_valid_memory_evidence_link(
    *,
    link: MemoryEvidenceLink,
    record: MemoryRecord,
    chunk_projects: dict[str, str],
    requirement_projects: dict[str, str],
    evidence_projects: dict[str, str],
    chat_sources: dict[str, tuple[str | None, str]],
    audit_projects: dict[str, str],
) -> bool:
    if link.source_type == "human_decision":
        return bool(record.created_by_actor_id) and link.source_id == record.created_by_actor_id
    if link.source_type == "knowledge_chunk":
        return chunk_projects.get(link.source_id) == record.project_id
    if link.source_type == "requirement_item":
        return requirement_projects.get(link.source_id) == record.project_id
    if link.source_type == "evidence_item":
        return evidence_projects.get(link.source_id) == record.project_id
    if link.source_type == "chat_message":
        return chat_sources.get(link.source_id) == (record.project_id, record.created_by_actor_id)
    if link.source_type == "audit_event":
        return audit_projects.get(link.source_id) == record.project_id
    return False


__all__ = [
    "RankedMemoryRecord",
    "has_visible_memory",
    "search_dense_memory_candidates",
    "search_fts_memory_candidates",
    "search_trigram_memory_candidates",
    "list_active_preference_memory",
    "valid_memory_evidence_links",
]
