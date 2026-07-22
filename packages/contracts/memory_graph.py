"""Typed, evidence-bound proposals for a future reviewed Bid Wiki graph.

This module deliberately models *proposals*, not graph-database rows. A model
or human may suggest entities and relations, but a product workflow must still
validate evidence, obtain approval, and materialize a durable projection.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .memory import MemoryCitation, MemoryCitationSource


MEMORY_GRAPH_SCHEMA_VERSION = "bidpilot.memory-graph/v1"
MEMORY_GRAPH_NORMALIZER_VERSION = "memory-graph-normalizer-v1"
_LOCAL_ID_PATTERN = r"^[a-z][a-z0-9_-]{0,39}$"


class MemoryGraphEntityType(StrEnum):
    BIDDER = "bidder"
    ISSUER = "issuer"
    BID_PROJECT = "bid_project"
    REQUIREMENT = "requirement"
    QUALIFICATION = "qualification"
    DELIVERABLE = "deliverable"
    DEADLINE = "deadline"
    STANDARD = "standard"
    DOCUMENT = "document"
    LOCATION = "location"
    AMOUNT = "amount"
    RISK = "risk"


class MemoryGraphRelationPredicate(StrEnum):
    APPLIES_TO = "applies_to"
    CONFLICTS_WITH = "conflicts_with"
    DEPENDS_ON = "depends_on"
    HAS_DEADLINE = "has_deadline"
    ISSUED_BY = "issued_by"
    REQUIRES = "requires"
    REQUIRES_EVIDENCE = "requires_evidence"
    REFERENCES = "references"
    SUBMITTED_BY = "submitted_by"


def normalize_memory_graph_name(value: str) -> str:
    """Make a stable, language-safe identity key without translating content."""
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def memory_graph_source_snapshot_fingerprint(
    *,
    policy_version: str,
    memory_record_id: str,
    title: str,
    body_markdown: str,
    citations: tuple[MemoryCitation, ...],
) -> str:
    """Fingerprint the exact approved source snapshot used by an extractor."""
    if not policy_version or not memory_record_id:
        raise ValueError("memory graph snapshots require policy and source identifiers")
    payload = {
        "policy_version": policy_version,
        "memory_record_id": memory_record_id,
        "record_content_digest": hashlib.sha256(f"{title}\0{body_markdown}".encode("utf-8")).hexdigest(),
        "evidence": sorted((citation.source_type.value, citation.source_id) for citation in citations),
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()


class _MemoryGraphModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class MemoryGraphEvidenceRef(_MemoryGraphModel):
    source_type: MemoryCitationSource
    source_id: str = Field(min_length=1, max_length=80)

    @property
    def key(self) -> tuple[str, str]:
        return (self.source_type.value, self.source_id)


class MemoryGraphEntityProposal(_MemoryGraphModel):
    local_id: str = Field(min_length=1, max_length=40, pattern=_LOCAL_ID_PATTERN)
    canonical_name: str = Field(min_length=1, max_length=240)
    entity_type: MemoryGraphEntityType
    aliases: tuple[str, ...] = Field(default=(), max_length=12)
    evidence_refs: tuple[MemoryGraphEvidenceRef, ...] = Field(min_length=1, max_length=12)
    confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator("aliases")
    @classmethod
    def validate_aliases(cls, aliases: tuple[str, ...]) -> tuple[str, ...]:
        normalized = [normalize_memory_graph_name(alias) for alias in aliases]
        if any(not alias for alias in normalized):
            raise ValueError("memory graph aliases must not be blank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("memory graph aliases must be unique")
        return aliases

    @field_validator("canonical_name")
    @classmethod
    def validate_canonical_name(cls, canonical_name: str) -> str:
        if not normalize_memory_graph_name(canonical_name):
            raise ValueError("memory graph canonical names must not be blank")
        return canonical_name

    @field_validator("evidence_refs")
    @classmethod
    def validate_evidence_refs(cls, evidence_refs: tuple[MemoryGraphEvidenceRef, ...]) -> tuple[MemoryGraphEvidenceRef, ...]:
        if len({evidence_ref.key for evidence_ref in evidence_refs}) != len(evidence_refs):
            raise ValueError("memory graph evidence refs must be unique")
        return evidence_refs

    @property
    def semantic_key(self) -> tuple[str, str]:
        return (self.entity_type.value, normalize_memory_graph_name(self.canonical_name))


class MemoryGraphRelationProposal(_MemoryGraphModel):
    subject_local_id: str = Field(min_length=1, max_length=40, pattern=_LOCAL_ID_PATTERN)
    predicate: MemoryGraphRelationPredicate
    object_local_id: str = Field(min_length=1, max_length=40, pattern=_LOCAL_ID_PATTERN)
    evidence_refs: tuple[MemoryGraphEvidenceRef, ...] = Field(min_length=1, max_length=12)
    confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator("evidence_refs")
    @classmethod
    def validate_evidence_refs(cls, evidence_refs: tuple[MemoryGraphEvidenceRef, ...]) -> tuple[MemoryGraphEvidenceRef, ...]:
        if len({evidence_ref.key for evidence_ref in evidence_refs}) != len(evidence_refs):
            raise ValueError("memory graph evidence refs must be unique")
        return evidence_refs


class MemoryGraphProposal(_MemoryGraphModel):
    """One source-grounded graph proposal attached to a memory record."""

    schema_version: Literal[MEMORY_GRAPH_SCHEMA_VERSION] = MEMORY_GRAPH_SCHEMA_VERSION
    entities: tuple[MemoryGraphEntityProposal, ...] = Field(min_length=1, max_length=24)
    relations: tuple[MemoryGraphRelationProposal, ...] = Field(default=(), max_length=48)

    @model_validator(mode="after")
    def validate_graph_shape(self) -> MemoryGraphProposal:
        local_ids = [entity.local_id for entity in self.entities]
        if len(local_ids) != len(set(local_ids)):
            raise ValueError("memory graph entity local ids must be unique")

        semantic_keys = [entity.semantic_key for entity in self.entities]
        if len(semantic_keys) != len(set(semantic_keys)):
            raise ValueError("memory graph must not contain duplicate canonical entities")

        known_local_ids = set(local_ids)
        relation_keys: set[tuple[str, str, str]] = set()
        for relation in self.relations:
            if relation.subject_local_id not in known_local_ids or relation.object_local_id not in known_local_ids:
                raise ValueError("memory graph relation endpoints must reference declared entities")
            if relation.subject_local_id == relation.object_local_id:
                raise ValueError("memory graph self-relations are not supported")
            key = (relation.subject_local_id, relation.predicate.value, relation.object_local_id)
            if key in relation_keys:
                raise ValueError("memory graph relations must be unique")
            relation_keys.add(key)
        return self

    def validate_evidence_sources(self, available_evidence_refs: set[tuple[str, str]]) -> None:
        """Require each proposed graph item to cite this record's valid evidence."""
        if not available_evidence_refs:
            raise ValueError("memory graph proposals require validated memory evidence")
        for entity in self.entities:
            _validate_evidence_subset(entity.evidence_refs, available_evidence_refs, "entity")
        for relation in self.relations:
            _validate_evidence_subset(relation.evidence_refs, available_evidence_refs, "relation")


def memory_graph_proposal_fingerprint(proposal: MemoryGraphProposal) -> str:
    """Create the stable review-decision fingerprint for one typed proposal."""
    encoded = json.dumps(
        proposal.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def memory_graph_item_id(proposal_fingerprint: str, item_type: Literal["entity", "relation"], item_key: Any) -> str:
    """Generate an opaque review identifier without exposing local graph ids."""
    if not proposal_fingerprint:
        raise ValueError("memory graph item ids require a proposal fingerprint")
    encoded = json.dumps(item_key, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(f"{proposal_fingerprint}\0{item_type}\0{encoded}".encode("utf-8")).hexdigest()[:32]
    return f"gri_{digest}"


def _validate_evidence_subset(
    evidence_refs: tuple[MemoryGraphEvidenceRef, ...],
    available_evidence_refs: set[tuple[str, str]],
    item_type: str,
) -> None:
    unknown_evidence_refs = {evidence_ref.key for evidence_ref in evidence_refs} - available_evidence_refs
    if unknown_evidence_refs:
        raise ValueError(f"memory graph {item_type} references unavailable evidence")


__all__ = [
    "MEMORY_GRAPH_NORMALIZER_VERSION",
    "MEMORY_GRAPH_SCHEMA_VERSION",
    "MemoryGraphEvidenceRef",
    "MemoryGraphEntityProposal",
    "MemoryGraphEntityType",
    "MemoryGraphProposal",
    "MemoryGraphRelationPredicate",
    "MemoryGraphRelationProposal",
    "memory_graph_item_id",
    "memory_graph_proposal_fingerprint",
    "memory_graph_source_snapshot_fingerprint",
    "normalize_memory_graph_name",
]
