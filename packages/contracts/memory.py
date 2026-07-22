"""Framework-neutral contracts for governed agent memory and Bid Wiki context."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MemoryScope(StrEnum):
    USER_PRIVATE = "user_private"
    PROJECT_SHARED = "project_shared"
    ORG_SHARED = "org_shared"


class MemoryKind(StrEnum):
    PREFERENCE = "preference"
    FACT = "fact"
    DECISION = "decision"
    PROCEDURE = "procedure"
    RISK = "risk"
    SUMMARY = "summary"
    ENTITY_NOTE = "entity_note"


class MemoryStatus(StrEnum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"
    DELETED = "deleted"


class MemoryProposalOrigin(StrEnum):
    USER = "user"
    HUMAN = "human"
    SYSTEM = "system"


class MemoryCitationSource(StrEnum):
    KNOWLEDGE_CHUNK = "knowledge_chunk"
    REQUIREMENT_ITEM = "requirement_item"
    EVIDENCE_ITEM = "evidence_item"
    CHAT_MESSAGE = "chat_message"
    AUDIT_EVENT = "audit_event"
    HUMAN_DECISION = "human_decision"


class _MemoryContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MemoryCitation(_MemoryContract):
    source_type: MemoryCitationSource
    source_id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=500)
    locator_json: dict[str, object] | None = None


class MemoryProposal(_MemoryContract):
    org_id: str = Field(min_length=1, max_length=36)
    project_id: str | None = Field(default=None, min_length=1, max_length=36)
    owner_user_id: str | None = Field(default=None, min_length=1, max_length=36)
    scope: MemoryScope
    kind: MemoryKind
    title: str = Field(min_length=1, max_length=240)
    body_markdown: str = Field(min_length=1, max_length=12000)
    structured_data_json: dict[str, object] | None = None
    origin: MemoryProposalOrigin
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_scope_and_evidence(self) -> MemoryProposal:
        if self.scope is MemoryScope.PROJECT_SHARED and not self.project_id:
            raise ValueError("project-shared memory requires project_id")
        if self.scope is MemoryScope.USER_PRIVATE and not self.owner_user_id:
            raise ValueError("user-private memory requires owner_user_id")
        if self.origin is MemoryProposalOrigin.SYSTEM and not self.evidence_ids:
            raise ValueError("system-generated memory requires evidence_ids")
        return self


class MemoryContextItem(_MemoryContract):
    record_id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=1, max_length=240)
    body_markdown: str = Field(min_length=1, max_length=12000)
    scope: MemoryScope
    kind: MemoryKind
    owner_user_id: str | None = Field(default=None, min_length=1, max_length=36)
    citations: tuple[MemoryCitation, ...] = Field(default_factory=tuple, max_length=32)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_provenance(self) -> MemoryContextItem:
        if self.scope is MemoryScope.USER_PRIVATE and not self.owner_user_id:
            raise ValueError("user-private memory context requires owner_user_id")
        if not self.citations:
            raise ValueError("memory context item requires provenance")
        return self


class MemoryContextPack(_MemoryContract):
    org_id: str = Field(min_length=1, max_length=36)
    user_id: str = Field(min_length=1, max_length=36)
    project_id: str | None = Field(default=None, min_length=1, max_length=36)
    memory_version: str = Field(min_length=1, max_length=128)
    items: tuple[MemoryContextItem, ...] = Field(default_factory=tuple, max_length=24)
    degraded_reasons: tuple[str, ...] = Field(default_factory=tuple, max_length=16)

    @model_validator(mode="after")
    def validate_private_ownership(self) -> MemoryContextPack:
        for item in self.items:
            if item.scope is MemoryScope.USER_PRIVATE and item.owner_user_id != self.user_id:
                raise ValueError("private memory context belongs to a different user")
        return self


__all__ = [
    "MemoryCitation",
    "MemoryCitationSource",
    "MemoryContextItem",
    "MemoryContextPack",
    "MemoryKind",
    "MemoryProposal",
    "MemoryProposalOrigin",
    "MemoryScope",
    "MemoryStatus",
]
