"""Framework-neutral contracts for project-scoped evidence retrieval."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


NORMALIZER_VERSION = "bidpilot-lexical-v1"
RRF_K = 60

_CJK_RUN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")
_LATIN_OR_NUMBER = re.compile(r"[a-z0-9][a-z0-9._/+-]*")


class EmbeddingOutcomeStatus(StrEnum):
    SUCCESS = "success"
    BUDGET_EXHAUSTED = "budget_exhausted"
    NOT_CONFIGURED = "not_configured"
    TRANSIENT_FAILURE = "transient_failure"
    PERMANENT_FAILURE = "permanent_failure"
    DIMENSION_MISMATCH = "dimension_mismatch"


class CitationValidationStatus(StrEnum):
    VERIFIED = "verified"
    PARTIAL = "partial"
    INVALID = "invalid"


class RerankOutcomeStatus(StrEnum):
    DISABLED = "disabled"
    SUCCESS = "success"
    TRANSIENT_FAILURE = "transient_failure"
    PERMANENT_FAILURE = "permanent_failure"


class _RetrievalContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RetrievalProfile(_RetrievalContract):
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=255)
    dimensions: int = Field(ge=1, le=1536)
    normalizer_version: str = Field(min_length=1, max_length=100)

    @property
    def identifier(self) -> str:
        return ":".join((self.provider, self.model, str(self.dimensions), self.normalizer_version))


class EmbeddingOutcome(_RetrievalContract):
    status: EmbeddingOutcomeStatus
    profile_id: str | None = Field(default=None, min_length=1, max_length=500)
    vector: list[float] | None = None
    token_count: int = Field(default=0, ge=0)
    usage_reported: bool = False
    error_code: str | None = Field(default=None, min_length=1, max_length=100)

    @property
    def is_success(self) -> bool:
        return self.status is EmbeddingOutcomeStatus.SUCCESS

    @model_validator(mode="after")
    def validate_outcome(self) -> EmbeddingOutcome:
        if self.is_success:
            if self.vector is None or self.profile_id is None:
                raise ValueError("successful embedding requires a vector and profile_id")
            if not self.vector:
                raise ValueError("successful embedding requires a non-empty vector")
            return self
        if self.vector is not None:
            raise ValueError("non-successful embedding outcome cannot carry a vector")
        return self


class CitationLocator(_RetrievalContract):
    source_document_id: str = Field(min_length=1, max_length=36)
    chunk_index: int = Field(ge=0)
    page: int | None = Field(default=None, ge=1)
    heading: str | None = Field(default=None, max_length=1000)
    table: str | None = Field(default=None, max_length=1000)
    text_anchor: str | None = Field(default=None, max_length=2000)
    validation_status: CitationValidationStatus = CitationValidationStatus.PARTIAL
    validation_reason: str | None = Field(default=None, max_length=500)


class RetrievalCandidate(_RetrievalContract):
    chunk_id: str = Field(min_length=1, max_length=36)
    project_id: str = Field(min_length=1, max_length=36)
    source_document_id: str = Field(min_length=1, max_length=36)
    content: str = Field(min_length=1)
    locator: CitationLocator
    dense_rank: int | None = Field(default=None, ge=1)
    sparse_rank: int | None = Field(default=None, ge=1)
    fused_rank: int = Field(ge=1)
    rerank_score: float | None = None
    final_score: float = Field(ge=0)
    methods: tuple[Literal["dense", "fts", "trigram", "rerank"], ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_locator_source(self) -> RetrievalCandidate:
        if self.locator.source_document_id != self.source_document_id:
            raise ValueError("locator source_document_id must match candidate source_document_id")
        return self


class RetrievalTrace(_RetrievalContract):
    profile_id: str | None = Field(default=None, min_length=1, max_length=500)
    query_kind: str = Field(min_length=1, max_length=80)
    dense_candidate_count: int = Field(default=0, ge=0)
    fts_candidate_count: int = Field(default=0, ge=0)
    trigram_candidate_count: int = Field(default=0, ge=0)
    fused_candidate_count: int = Field(default=0, ge=0)
    reranked_candidate_count: int = Field(default=0, ge=0)
    returned_candidate_count: int = Field(default=0, ge=0)
    degraded_reasons: tuple[str, ...] = ()
    latency_ms: int = Field(default=0, ge=0)


class RerankOutcome(_RetrievalContract):
    status: RerankOutcomeStatus
    scores: dict[str, float] = Field(default_factory=dict)
    error_code: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_scores(self) -> RerankOutcome:
        if self.status is RerankOutcomeStatus.SUCCESS:
            if not self.scores:
                raise ValueError("successful rerank requires at least one score")
            return self
        if self.scores:
            raise ValueError("non-successful rerank outcome cannot carry scores")
        return self


class FusedRetrievalCandidate(_RetrievalContract):
    chunk_id: str = Field(min_length=1, max_length=36)
    method_ranks: dict[str, int] = Field(min_length=1)
    score: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_method_ranks(self) -> FusedRetrievalCandidate:
        if any(not method or rank < 1 for method, rank in self.method_ranks.items()):
            raise ValueError("method ranks require non-empty methods and positive ranks")
        return self


class RetrievalResult(_RetrievalContract):
    project_id: str = Field(min_length=1, max_length=36)
    profile_id: str | None = Field(default=None, min_length=1, max_length=500)
    candidates: tuple[RetrievalCandidate, ...] = ()
    degraded_reasons: tuple[str, ...] = ()
    trace: RetrievalTrace | None = None

    @model_validator(mode="after")
    def validate_project_scope_and_deduplication(self) -> RetrievalResult:
        seen_chunk_ids: set[str] = set()
        for candidate in self.candidates:
            if candidate.project_id != self.project_id:
                raise ValueError("candidate project_id must match result project_id")
            if candidate.chunk_id in seen_chunk_ids:
                raise ValueError("duplicate chunk_id in retrieval result")
            seen_chunk_ids.add(candidate.chunk_id)
        return self


def normalize_retrieval_text(value: str) -> str:
    """Build FTS-friendly terms while preserving CJK phrase recall with bigrams."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    terms: list[str] = []
    cursor = 0

    for match in _CJK_RUN.finditer(normalized):
        terms.extend(_LATIN_OR_NUMBER.findall(normalized[cursor:match.start()]))
        cjk_run = match.group()
        if len(cjk_run) == 1:
            terms.append(cjk_run)
        else:
            terms.extend(cjk_run[index:index + 2] for index in range(len(cjk_run) - 1))
        cursor = match.end()

    terms.extend(_LATIN_OR_NUMBER.findall(normalized[cursor:]))
    return " ".join(terms)


def reciprocal_rank_fusion(
    rankings: Mapping[str, Sequence[str]],
    *,
    rrf_k: int = RRF_K,
) -> tuple[FusedRetrievalCandidate, ...]:
    """Fuse independently ranked chunk ids with deterministic reciprocal ranks."""
    if rrf_k < 1:
        raise ValueError("rrf_k must be positive")

    scores: dict[str, float] = {}
    ranks_by_chunk: dict[str, dict[str, int]] = {}
    for method, chunk_ids in rankings.items():
        if not method:
            raise ValueError("retrieval method must be non-empty")
        seen_in_method: set[str] = set()
        for rank, chunk_id in enumerate(chunk_ids, start=1):
            if not chunk_id:
                raise ValueError("ranked chunk id must be non-empty")
            if chunk_id in seen_in_method:
                continue
            seen_in_method.add(chunk_id)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
            ranks_by_chunk.setdefault(chunk_id, {})[method] = rank

    fused = [
        FusedRetrievalCandidate(
            chunk_id=chunk_id,
            method_ranks=ranks_by_chunk[chunk_id],
            score=score,
        )
        for chunk_id, score in scores.items()
    ]
    return tuple(
        sorted(
            fused,
            key=lambda candidate: (
                -candidate.score,
                min(candidate.method_ranks.values()),
                candidate.chunk_id,
            ),
        )
    )


__all__ = [
    "CitationLocator",
    "CitationValidationStatus",
    "EmbeddingOutcome",
    "EmbeddingOutcomeStatus",
    "FusedRetrievalCandidate",
    "NORMALIZER_VERSION",
    "RRF_K",
    "RerankOutcome",
    "RerankOutcomeStatus",
    "RetrievalCandidate",
    "RetrievalProfile",
    "RetrievalResult",
    "RetrievalTrace",
    "normalize_retrieval_text",
    "reciprocal_rank_fusion",
]
