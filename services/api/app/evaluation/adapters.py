"""Normalize current BidPilot Requirement Ledger snapshots for BidBench."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator

from contracts import (
    BidBenchCandidate,
    BidBenchCandidateClaim,
    BidBenchCandidateRequirement,
    BidBenchLocator,
    CoverageStatus,
    RequirementType,
)


class CurrentBidRequirementProfileSnapshot(BaseModel):
    """Subset of ``BidRequirementProfileRead`` needed for offline scoring."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    bid_category: str = "technical"
    is_mandatory: bool = False
    coverage_status: str = "uncovered"


class CurrentEvidenceLinkSnapshot(BaseModel):
    """Subset of ``RequirementEvidenceLinkRead`` needed for offline scoring."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    evidence_id: str = Field(min_length=1)
    relation_type: str = "supports"


class CurrentClaimSnapshot(BaseModel):
    """Subset of ``RequirementClaimRead`` needed for offline scoring."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    id: str = Field(min_length=1)
    claim_text: str = Field(min_length=1)
    claim_type: str = "factual"
    status: str = "draft"
    evidence_ids: list[str] = Field(default_factory=list)


class CurrentRequirementSnapshot(BaseModel):
    """Stable current Requirement API fields used by the baseline adapter."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    section_key: str = Field(min_length=1)
    requirement_text: str = Field(min_length=1)
    priority: str = "normal"
    status: str = "draft"
    source_document_id: str | None = None
    source_locator_json: dict[str, Any] | None = None
    extraction_confidence: float | None = Field(default=None, ge=0, le=1)
    bid_profile: CurrentBidRequirementProfileSnapshot | None = None
    evidence_links: list[CurrentEvidenceLinkSnapshot] = Field(default_factory=list)
    claims: list[CurrentClaimSnapshot] = Field(default_factory=list)


class CurrentPipelineTraceMap(BaseModel):
    """Maps platform ids to frozen BidBench source and evidence ids.

    The map is supplied by the evaluator. It is never inferred from filenames,
    document text, or an LLM, because a guessed mapping would overstate quality.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_document_ids: dict[str, str] = Field(default_factory=dict)
    evidence_ids: dict[str, str] = Field(default_factory=dict)

    @field_validator("source_document_ids", "evidence_ids")
    @classmethod
    def require_nonempty_mapping_values(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not source_id or not benchmark_id for source_id, benchmark_id in value.items()):
            raise ValueError("trace-map ids must be non-empty")
        return value


_REQUIREMENT_LIST = TypeAdapter(list[CurrentRequirementSnapshot])


def load_current_pipeline_trace_map(path: Path) -> CurrentPipelineTraceMap:
    """Load a reviewed platform-id to BidBench-id trace map from JSON."""

    try:
        return CurrentPipelineTraceMap.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid BidBench trace map: {path}") from exc


def build_candidate_from_requirement_snapshot(
    *,
    snapshot_path: Path,
    dataset_id: str,
    candidate_id: str,
    git_commit: str | None = None,
    trace_map: CurrentPipelineTraceMap | None = None,
    provider: str | None = None,
    model: str | None = None,
    prompt_version: str = "current-requirement-api-v2",
    run_number: int = 1,
    latency_ms: int | None = None,
    estimated_cost_usd: float | None = None,
) -> BidBenchCandidate:
    """Convert a saved Requirement Ledger response into a scored candidate.

    A source locator or evidence reference only survives conversion when the
    evaluator supplies a reviewed trace map. This makes an absent mapping show
    up as missing traceability instead of receiving accidental benchmark credit.
    """

    requirements, embedded_trace_map = _load_requirement_snapshot(snapshot_path)
    effective_trace_map = trace_map or embedded_trace_map or CurrentPipelineTraceMap()
    project_ids = {requirement.project_id for requirement in requirements}
    if len(project_ids) > 1:
        raise ValueError("snapshot contains requirements from multiple projects")

    candidate_requirements = [
        _to_candidate_requirement(requirement, effective_trace_map)
        for requirement in requirements
    ]
    candidate_claims = _to_candidate_claims(requirements, effective_trace_map)

    return BidBenchCandidate(
        schema_version="1.0",
        dataset_id=dataset_id,
        candidate_id=candidate_id,
        system_name="bidpilot-current-requirement-api",
        git_commit=git_commit,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        run_number=run_number,
        generated_at=datetime.now(UTC),
        latency_ms=latency_ms,
        estimated_cost_usd=estimated_cost_usd,
        requirements=candidate_requirements,
        claims=candidate_claims,
    )


def _load_requirement_snapshot(
    snapshot_path: Path,
) -> tuple[list[CurrentRequirementSnapshot], CurrentPipelineTraceMap | None]:
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid requirement snapshot: {snapshot_path}") from exc

    embedded_trace_map: CurrentPipelineTraceMap | None = None
    if isinstance(payload, dict):
        if "requirements" not in payload or not isinstance(payload["requirements"], list):
            raise ValueError("snapshot object must contain a requirements list")
        requirements_payload = payload["requirements"]
        if "trace_map" in payload:
            try:
                embedded_trace_map = CurrentPipelineTraceMap.model_validate(payload["trace_map"])
            except ValidationError as exc:
                raise ValueError("snapshot trace_map is invalid") from exc
    elif isinstance(payload, list):
        requirements_payload = payload
    else:
        raise ValueError("snapshot must be a requirement list or an object containing requirements")

    try:
        return _REQUIREMENT_LIST.validate_python(requirements_payload), embedded_trace_map
    except ValidationError as exc:
        raise ValueError("snapshot requirements are invalid") from exc


def _to_candidate_requirement(
    requirement: CurrentRequirementSnapshot,
    trace_map: CurrentPipelineTraceMap,
) -> BidBenchCandidateRequirement:
    profile = requirement.bid_profile
    is_mandatory = profile.is_mandatory if profile is not None else _priority_is_mandatory(requirement.priority)
    category = profile.bid_category if profile is not None else ""
    coverage_status = profile.coverage_status if profile is not None else "uncovered"

    return BidBenchCandidateRequirement(
        id=requirement.id,
        normalized_text=requirement.requirement_text,
        requirement_type=_to_requirement_type(category, is_mandatory),
        is_mandatory=is_mandatory,
        coverage_status=_to_coverage_status(coverage_status),
        locators=_to_candidate_locators(requirement, trace_map),
        evidence_ids=_mapped_evidence_ids(
            (
                link.evidence_id
                for link in requirement.evidence_links
                if link.relation_type.casefold() == "supports"
            ),
            trace_map,
        ),
        confidence=requirement.extraction_confidence,
    )


def _to_candidate_claims(
    requirements: Iterable[CurrentRequirementSnapshot],
    trace_map: CurrentPipelineTraceMap,
) -> list[BidBenchCandidateClaim]:
    claims_by_id: dict[str, dict[str, Any]] = {}
    for requirement in requirements:
        for claim in requirement.claims:
            existing = claims_by_id.get(claim.id)
            if existing is not None and existing["text"] != claim.claim_text:
                raise ValueError(f"claim {claim.id!r} has conflicting text in snapshot")
            entry = claims_by_id.setdefault(
                claim.id,
                {
                    "id": claim.id,
                    "text": claim.claim_text,
                    "requirement_ids": [],
                    "evidence_ids": [],
                    "is_inference": claim.claim_type.casefold() in {"inference", "inferred"},
                    "accepted": claim.status.casefold() in {"verified", "approved"},
                },
            )
            if requirement.id not in entry["requirement_ids"]:
                entry["requirement_ids"].append(requirement.id)
            for evidence_id in _mapped_evidence_ids(claim.evidence_ids, trace_map):
                if evidence_id not in entry["evidence_ids"]:
                    entry["evidence_ids"].append(evidence_id)

    return [BidBenchCandidateClaim(**claim) for claim in claims_by_id.values()]


def _to_candidate_locators(
    requirement: CurrentRequirementSnapshot,
    trace_map: CurrentPipelineTraceMap,
) -> list[BidBenchLocator]:
    if not requirement.source_document_id or requirement.source_locator_json is None:
        return []
    source_id = trace_map.source_document_ids.get(requirement.source_document_id)
    if source_id is None:
        return []

    locator_payload = {
        "source_id": source_id,
        **{
            field: requirement.source_locator_json[field]
            for field in ("page", "section", "table", "text_anchor", "bbox")
            if field in requirement.source_locator_json
        },
    }
    try:
        return [BidBenchLocator.model_validate(locator_payload)]
    except ValidationError as exc:
        raise ValueError(
            f"requirement {requirement.id!r} has an invalid mapped source locator"
        ) from exc


def _mapped_evidence_ids(
    evidence_ids: Iterable[str],
    trace_map: CurrentPipelineTraceMap,
) -> list[str]:
    mapped: list[str] = []
    for evidence_id in evidence_ids:
        benchmark_evidence_id = trace_map.evidence_ids.get(evidence_id)
        if benchmark_evidence_id and benchmark_evidence_id not in mapped:
            mapped.append(benchmark_evidence_id)
    return mapped


def _to_requirement_type(category: str, is_mandatory: bool) -> RequirementType:
    try:
        return RequirementType(category.casefold())
    except ValueError:
        return RequirementType.MANDATORY if is_mandatory else RequirementType.TECHNICAL


def _to_coverage_status(value: str) -> CoverageStatus:
    try:
        return CoverageStatus(value.casefold())
    except ValueError as exc:
        raise ValueError(f"unsupported current coverage status: {value!r}") from exc


def _priority_is_mandatory(priority: str) -> bool:
    return priority.casefold() in {"high", "critical"}


__all__ = [
    "CurrentPipelineTraceMap",
    "CurrentRequirementSnapshot",
    "build_candidate_from_requirement_snapshot",
    "load_current_pipeline_trace_map",
]
