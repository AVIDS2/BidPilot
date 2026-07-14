"""Versioned contracts for BidPilot's offline quality benchmark."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RequirementType(StrEnum):
    MANDATORY = "mandatory"
    SCORED = "scored"
    QUALIFICATION = "qualification"
    COMMERCIAL = "commercial"
    TECHNICAL = "technical"
    DELIVERY = "delivery"
    FORMATTING = "formatting"
    SUBMISSION = "submission"


class CoverageStatus(StrEnum):
    UNCOVERED = "uncovered"
    PARTIAL = "partial"
    COVERED = "covered"
    DISPUTED = "disputed"
    NOT_APPLICABLE = "not_applicable"


class DatasetRole(StrEnum):
    DEVELOPMENT = "development"
    REGRESSION = "regression"
    HIDDEN = "hidden"


class DatasetOrigin(StrEnum):
    SYNTHETIC = "synthetic"
    PUBLIC = "public"
    ANONYMIZED = "anonymized"
    PRIVATE = "private"


class _ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BidBenchSource(_ContractModel):
    id: str = Field(min_length=1, max_length=100)
    path: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=255)
    source_type: str = Field(min_length=1, max_length=80)
    sha256: str | None = Field(default=None, min_length=64, max_length=64)


class BidBenchLocator(_ContractModel):
    source_id: str = Field(min_length=1, max_length=100)
    page: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, max_length=500)
    table: str | None = Field(default=None, max_length=500)
    text_anchor: str | None = Field(default=None, max_length=2000)
    bbox: tuple[float, float, float, float] | None = None

    @model_validator(mode="after")
    def require_position_hint(self) -> BidBenchLocator:
        if not any((self.page, self.section, self.table, self.text_anchor, self.bbox)):
            raise ValueError("locator requires at least one position hint")
        return self


class BidBenchRequirement(_ContractModel):
    id: str = Field(min_length=1, max_length=100)
    original_text: str = Field(min_length=1)
    normalized_text: str = Field(min_length=1)
    requirement_type: RequirementType
    is_mandatory: bool = False
    expected_coverage: CoverageStatus
    locators: list[BidBenchLocator] = Field(default_factory=list)
    expected_evidence_ids: list[str] = Field(default_factory=list)
    score_weight: float | None = Field(default=None, ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def require_mandatory_locator(self) -> BidBenchRequirement:
        if self.is_mandatory and not self.locators:
            raise ValueError("mandatory requirement must include a source locator")
        return self


class BidBenchEvidence(_ContractModel):
    id: str = Field(min_length=1, max_length=100)
    source_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1)
    locator: BidBenchLocator
    supports_requirement_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def match_locator_source(self) -> BidBenchEvidence:
        if self.locator.source_id != self.source_id:
            raise ValueError("evidence locator source must match evidence source")
        return self


class BidBenchDataset(_ContractModel):
    schema_version: Literal["1.0"]
    dataset_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    language: str = Field(default="zh-CN", min_length=2, max_length=20)
    dataset_role: DatasetRole
    origin_type: DatasetOrigin
    provenance: str = Field(min_length=1)
    license_id: str = Field(min_length=1, max_length=100)
    description: str | None = None
    sources: list[BidBenchSource] = Field(min_length=1)
    requirements: list[BidBenchRequirement] = Field(min_length=1)
    evidence: list[BidBenchEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> BidBenchDataset:
        source_ids = self._unique_ids("sources", self.sources)
        requirement_ids = self._unique_ids("requirements", self.requirements)
        evidence_ids = self._unique_ids("evidence", self.evidence)

        for requirement in self.requirements:
            for locator in requirement.locators:
                if locator.source_id not in source_ids:
                    raise ValueError(
                        f"requirement {requirement.id!r} references unknown source {locator.source_id!r}"
                    )
            for evidence_id in requirement.expected_evidence_ids:
                if evidence_id not in evidence_ids:
                    raise ValueError(
                        f"requirement {requirement.id!r} references unknown evidence {evidence_id!r}"
                    )

        for evidence in self.evidence:
            if evidence.source_id not in source_ids:
                raise ValueError(
                    f"evidence {evidence.id!r} references unknown source {evidence.source_id!r}"
                )
            for requirement_id in evidence.supports_requirement_ids:
                if requirement_id not in requirement_ids:
                    raise ValueError(
                        f"evidence {evidence.id!r} references unknown requirement {requirement_id!r}"
                    )

        return self

    @staticmethod
    def _unique_ids(collection_name: str, items: list[object]) -> set[str]:
        ids = [getattr(item, "id") for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{collection_name} contains a duplicate id")
        return set(ids)


class BidBenchCandidateRequirement(_ContractModel):
    id: str = Field(min_length=1, max_length=100)
    ground_truth_id: str | None = Field(default=None, min_length=1, max_length=100)
    normalized_text: str = Field(min_length=1)
    requirement_type: RequirementType
    is_mandatory: bool = False
    coverage_status: CoverageStatus
    locators: list[BidBenchLocator] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)


class BidBenchCandidateClaim(_ContractModel):
    id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1)
    requirement_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    is_inference: bool = False
    accepted: bool = True


class BidBenchCandidate(_ContractModel):
    schema_version: Literal["1.0"]
    dataset_id: str = Field(min_length=1, max_length=100)
    candidate_id: str = Field(min_length=1, max_length=200)
    system_name: str = Field(min_length=1, max_length=200)
    git_commit: str | None = Field(default=None, max_length=64)
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=200)
    prompt_version: str | None = Field(default=None, max_length=100)
    run_number: int = Field(default=1, ge=1)
    generated_at: datetime | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    requirements: list[BidBenchCandidateRequirement] = Field(default_factory=list)
    claims: list[BidBenchCandidateClaim] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> BidBenchCandidate:
        BidBenchDataset._unique_ids("candidate requirements", self.requirements)
        BidBenchDataset._unique_ids("candidate claims", self.claims)
        return self


__all__ = [
    "BidBenchDataset",
    "BidBenchCandidate",
    "BidBenchCandidateClaim",
    "BidBenchCandidateRequirement",
    "BidBenchEvidence",
    "BidBenchLocator",
    "BidBenchRequirement",
    "BidBenchSource",
    "CoverageStatus",
    "DatasetOrigin",
    "DatasetRole",
    "RequirementType",
]
