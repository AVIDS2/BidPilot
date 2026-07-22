from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.memory import MemoryCitation, MemoryContextItem, MemoryKind, MemoryScope, MemoryStatus
from contracts.memory_graph import MemoryGraphEntityType, MemoryGraphRelationPredicate


class MemoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    scope: MemoryScope
    project_id: str | None = Field(default=None, min_length=1, max_length=36)
    kind: MemoryKind
    title: str = Field(min_length=1, max_length=240)
    body_markdown: str = Field(min_length=1, max_length=12000)
    structured_data_json: dict[str, object] | None = None
    citations: list[MemoryCitation] = Field(default_factory=list, max_length=32)
    expires_at: datetime | None = None


class MemoryGraphEntityRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    canonical_name: str
    entity_type: MemoryGraphEntityType
    evidence_labels: tuple[str, ...]
    review_status: Literal["pending", "accepted", "rejected"]
    review_note: str | None = None


class MemoryGraphRelationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    subject: str
    predicate: MemoryGraphRelationPredicate
    object: str
    evidence_labels: tuple[str, ...]
    review_status: Literal["pending", "accepted", "rejected"]
    review_note: str | None = None


class MemoryGraphProposalRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    entities: tuple[MemoryGraphEntityRead, ...]
    relations: tuple[MemoryGraphRelationRead, ...]


class MemoryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    org_id: str
    project_id: str | None
    owner_user_id: str | None
    scope: MemoryScope
    kind: MemoryKind
    status: MemoryStatus
    title: str
    body_markdown: str
    citations: list[MemoryCitation]
    graph_proposal: MemoryGraphProposalRead | None = None
    expires_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


class MemoryPortfolioProjectRead(BaseModel):
    """Safe project-level knowledge health for the Workbench portfolio."""

    project_id: str
    project_name: str
    active_shared_count: int
    proposed_shared_count: int | None
    latest_shared_memory_at: datetime | None
    latest_compilation_status: str | None
    latest_compilation_at: datetime | None


class MemoryEvidenceMapNodeRead(BaseModel):
    """A safe, graph-renderable node for one authorized project only."""

    model_config = ConfigDict(extra="forbid")

    id: str
    node_type: Literal["memory", "source"]
    label: str
    memory_kind: str | None = None
    source_type: str | None = None


class MemoryEvidenceMapEdgeRead(BaseModel):
    """A citation edge; it intentionally does not claim factual sufficiency."""

    model_config = ConfigDict(extra="forbid")

    id: str
    source: str
    target: str
    predicate: Literal["cites"]


class MemoryEvidenceMapRead(BaseModel):
    """Bounded project-shared provenance graph, not a graph database dump."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    nodes: tuple[MemoryEvidenceMapNodeRead, ...] = ()
    edges: tuple[MemoryEvidenceMapEdgeRead, ...] = ()
    truncated: bool = False


class MemoryGraphExtractionCreate(BaseModel):
    """Request one reviewable graph proposal from an active shared memory record."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_id: str = Field(min_length=1, max_length=36)
    memory_record_id: str = Field(min_length=1, max_length=36)
    provider_config_id: str | None = Field(default=None, min_length=1, max_length=36)
    reasoning_effort: Literal["low", "medium", "high", "extra", "max"] | None = None


class MemoryGraphExtractionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    runtime_run_id: str
    project_id: str
    memory_record_id: str
    status: str
    reused: bool = False


class MemoryGraphReviewDecisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    item_id: str = Field(min_length=1, max_length=80)
    decision: Literal["accepted", "rejected"]
    decision_note: str | None = Field(default=None, max_length=2_000)


class MemoryGraphReviewDecisionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    item_type: Literal["entity", "relation"]
    decision: Literal["accepted", "rejected"]
    decision_note: str | None
    reviewed_at: datetime | None


class MemoryContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_id: str | None = Field(default=None, min_length=1, max_length=36)
    query: str = Field(min_length=1, max_length=4_000)
    top_k: int = Field(default=8, ge=1, le=24)
    max_characters: int = Field(default=12_000, ge=256, le=24_000)


class MemoryContextRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str | None
    memory_version: str
    items: tuple[MemoryContextItem, ...]
    degraded_reasons: tuple[str, ...] = ()


class MemoryCompilationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_id: str = Field(min_length=1, max_length=36)
    bundle_id: str | None = Field(default=None, min_length=1, max_length=36)


class MemoryCompilationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    project_id: str
    bundle_id: str | None
    status: str
    input_source_count: int
    result_json: dict[str, object] | None
    error_code: str | None
    created_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
