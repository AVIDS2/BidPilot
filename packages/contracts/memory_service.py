"""Deterministic, provenance-preserving memory context packing for Agent runs."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from .memory import MemoryCitation, MemoryContextItem, MemoryContextPack, MemoryKind, MemoryScope
from .memory_repository import (
    RankedMemoryRecord,
    list_active_preference_memory,
    search_dense_memory_candidates,
    search_fts_memory_candidates,
    search_trigram_memory_candidates,
)
from .models import MemoryRecord
from .retrieval import normalize_retrieval_text, reciprocal_rank_fusion


_METHOD_ORDER = ("dense", "fts", "trigram")


def _utc_naive_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _add_ranked_records(
    rankings: dict[str, list[str]],
    records: dict[str, RankedMemoryRecord],
    method: str,
    candidates: Iterable[RankedMemoryRecord],
) -> None:
    method_candidates = list(candidates)
    rankings[method] = [candidate.record_id for candidate in method_candidates]
    for candidate in method_candidates:
        records.setdefault(candidate.record_id, candidate)


def _citations(record: MemoryRecord) -> tuple[MemoryCitation, ...]:
    citations: list[MemoryCitation] = []
    for link in sorted(
        record.evidence_links,
        key=lambda value: (value.source_type, value.source_id, value.evidence_role, value.id),
    ):
        try:
            citations.append(
                MemoryCitation(
                    source_type=link.source_type,
                    source_id=link.source_id,
                    label=link.label,
                    locator_json=link.locator_json,
                )
            )
        except ValueError:
            continue
    return tuple(citations)


def _compact_body(value: str, *, limit: int) -> str:
    body = value.strip()
    if len(body) <= limit:
        return body
    if limit <= 3:
        return body[:limit]
    return f"{body[: limit - 3].rstrip()}..."


def _memory_version(
    *,
    org_id: str,
    user_id: str,
    project_id: str | None,
    records: Iterable[MemoryRecord],
) -> str:
    parts = ["bidpilot-memory-context-v1", org_id, user_id, project_id or "-"]
    parts.extend(
        f"{record.id}:{record.updated_at.isoformat() if record.updated_at else '-'}"
        for record in records
    )
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_memory_context_pack(
    db: Session,
    *,
    org_id: str,
    user_id: str,
    project_id: str | None,
    raw_query: str,
    profile_id: str | None,
    query_embedding: list[float] | None,
    top_k: int,
    max_characters: int,
) -> MemoryContextPack:
    """Build a scope-safe context pack without ever fabricating semantic recall."""
    if top_k < 1:
        raise ValueError("top_k must be positive")
    if max_characters < 1:
        raise ValueError("max_characters must be positive")

    now = _utc_naive_now()
    candidate_limit = max(top_k * 4, 20)
    rankings: dict[str, list[str]] = {}
    records: dict[str, RankedMemoryRecord] = {}
    degraded_reasons: list[str] = []

    dense_candidates: list[RankedMemoryRecord] = []
    if profile_id and query_embedding:
        dense_candidates = search_dense_memory_candidates(
            db,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            profile_id=profile_id,
            query_embedding=query_embedding,
            now=now,
            top_k=candidate_limit,
        )
        _add_ranked_records(rankings, records, "dense", dense_candidates)
    else:
        degraded_reasons.append("dense_unavailable")

    normalized_query = normalize_retrieval_text(raw_query)
    fts_candidates = search_fts_memory_candidates(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=project_id,
        normalized_query=normalized_query,
        now=now,
        top_k=candidate_limit,
    )
    _add_ranked_records(rankings, records, "fts", fts_candidates)

    trigram_candidates = search_trigram_memory_candidates(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=project_id,
        raw_query=raw_query,
        now=now,
        top_k=candidate_limit,
    )
    _add_ranked_records(rankings, records, "trigram", trigram_candidates)

    fused = reciprocal_rank_fusion(rankings)
    always_on_preferences = list_active_preference_memory(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=project_id,
        now=now,
        top_k=min(top_k, 3),
    )
    ordered_records = [records[fused_record.chunk_id].record for fused_record in fused]
    seen_record_ids = {record.id for record in ordered_records}
    ordered_records.extend(record for record in always_on_preferences if record.id not in seen_record_ids)
    remaining_characters = max_characters
    selected_records: list[MemoryRecord] = []
    items: list[MemoryContextItem] = []
    invalid_provenance_count = 0

    for record in ordered_records:
        if len(items) >= top_k or remaining_characters <= 1:
            break
        citations = _citations(record)
        if not citations:
            invalid_provenance_count += 1
            continue
        try:
            scope = MemoryScope(record.scope)
            kind = MemoryKind(record.kind)
        except ValueError:
            invalid_provenance_count += 1
            continue

        title = record.title.strip()
        body_limit = remaining_characters - len(title)
        if body_limit < 1:
            break
        body = _compact_body(record.body_markdown, limit=body_limit)
        if not body:
            continue
        items.append(
            MemoryContextItem(
                record_id=record.id,
                title=title,
                body_markdown=body,
                scope=scope,
                kind=kind,
                owner_user_id=record.owner_user_id,
                citations=citations,
                expires_at=record.expires_at,
            )
        )
        selected_records.append(record)
        remaining_characters -= len(title) + len(body)

    if invalid_provenance_count:
        degraded_reasons.append("invalid_memory_provenance")
    if not items:
        degraded_reasons.append("no_memory_found")

    return MemoryContextPack(
        org_id=org_id,
        user_id=user_id,
        project_id=project_id,
        memory_version=_memory_version(
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            records=selected_records,
        ),
        items=tuple(items),
        degraded_reasons=tuple(degraded_reasons),
    )


__all__ = ["build_memory_context_pack"]
