"""Build redacted BidBench candidates from governed Claim Integrity runs.

The private manifest maps durable runtime records to frozen benchmark IDs. It
is intentionally never embedded in the generated candidate, which contains no
customer text, raw locators, or database identifiers.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Bundle,
    Claim,
    Deliverable,
    DeliverableSection,
    Evidence,
    ExecutionRun,
    Project,
    RequirementItem,
    RuntimeRun,
    SectionVersion,
    SourceDocument,
)
from contracts import (
    BidBenchCandidate,
    BidBenchCandidateClaim,
    BidBenchCandidateRequirement,
    BidBenchDataset,
    BidBenchLocator,
    CoverageStatus,
    EvaluationCaptureKind,
    EvaluationEvidenceProvenance,
    EvaluationReviewLevel,
    RequirementType,
    RuntimeRunKind,
    RuntimeRunStatus,
)

from .metrics import _locator_matches, _normalize_text


_SAFE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
_DRAFT_RUN_TYPES = {"draft_section", "redraft_section"}


class _ClaimIntegrityCaptureModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ClaimIntegrityRuntimeRequirementMap(_ClaimIntegrityCaptureModel):
    """Private mapping for one current Requirement Ledger item."""

    runtime_requirement_id: str = Field(min_length=1, max_length=100)
    candidate_requirement_id: str = Field(min_length=1, max_length=100, pattern=_SAFE_ID_PATTERN)
    benchmark_requirement_id: str | None = Field(default=None, min_length=1, max_length=100)


class ClaimIntegrityRuntimeSourceMap(_ClaimIntegrityCaptureModel):
    """Private source-document mapping; the candidate ID is safe to export."""

    runtime_source_document_id: str = Field(min_length=1, max_length=100)
    candidate_source_id: str = Field(min_length=1, max_length=100, pattern=_SAFE_ID_PATTERN)
    benchmark_source_id: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_known_source_uses_its_frozen_id(self) -> ClaimIntegrityRuntimeSourceMap:
        if self.benchmark_source_id and self.candidate_source_id != self.benchmark_source_id:
            raise ValueError("mapped benchmark source must use its frozen source id")
        return self


class ClaimIntegrityRuntimeEvidenceMap(_ClaimIntegrityCaptureModel):
    """Private Evidence mapping; unknown evidence retains an opaque ID."""

    runtime_evidence_id: str = Field(min_length=1, max_length=100)
    candidate_evidence_id: str = Field(min_length=1, max_length=100, pattern=_SAFE_ID_PATTERN)
    benchmark_evidence_id: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_known_evidence_uses_its_frozen_id(self) -> ClaimIntegrityRuntimeEvidenceMap:
        if self.benchmark_evidence_id and self.candidate_evidence_id != self.benchmark_evidence_id:
            raise ValueError("mapped benchmark evidence must use its frozen evidence id")
        return self


class ClaimIntegrityRuntimeClaimMap(_ClaimIntegrityCaptureModel):
    """Private Claim mapping with a redacted candidate identifier."""

    runtime_claim_id: str = Field(min_length=1, max_length=100)
    candidate_claim_id: str = Field(min_length=1, max_length=100, pattern=_SAFE_ID_PATTERN)


class ClaimIntegrityRuntimeCaptureManifest(_ClaimIntegrityCaptureModel):
    """Private, reviewed mapping for one redacted current-pipeline candidate."""

    schema_version: Literal["1.0"] = "1.0"
    dataset_id: str = Field(min_length=1, max_length=100)
    fixture_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    runtime_project_id: str = Field(min_length=1, max_length=100)
    execution_run_id: str = Field(min_length=1, max_length=100)
    section_version_id: str = Field(min_length=1, max_length=100)
    candidate_id: str = Field(min_length=1, max_length=200, pattern=_SAFE_ID_PATTERN)
    requirements: tuple[ClaimIntegrityRuntimeRequirementMap, ...] = Field(min_length=1)
    source_documents: tuple[ClaimIntegrityRuntimeSourceMap, ...] = ()
    evidence: tuple[ClaimIntegrityRuntimeEvidenceMap, ...] = ()
    claims: tuple[ClaimIntegrityRuntimeClaimMap, ...] = ()
    git_commit: str | None = Field(default=None, max_length=64)
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=255)
    prompt_version: str = Field(default="claim-integrity-runtime-v1", min_length=1, max_length=100)
    run_number: int = Field(default=1, ge=1)
    latency_ms: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    provenance: EvaluationEvidenceProvenance

    @model_validator(mode="after")
    def validate_unique_private_mappings(self) -> ClaimIntegrityRuntimeCaptureManifest:
        _validate_unique_mapping_values(
            self.requirements,
            "runtime_requirement_id",
            "runtime requirement",
        )
        _validate_unique_mapping_values(
            self.requirements,
            "candidate_requirement_id",
            "candidate requirement",
        )
        _validate_unique_mapping_values(
            self.source_documents,
            "runtime_source_document_id",
            "runtime source document",
        )
        _validate_unique_mapping_values(
            self.source_documents,
            "candidate_source_id",
            "candidate source",
        )
        _validate_unique_mapping_values(self.evidence, "runtime_evidence_id", "runtime evidence")
        _validate_unique_mapping_values(self.evidence, "candidate_evidence_id", "candidate evidence")
        _validate_unique_mapping_values(self.claims, "runtime_claim_id", "runtime claim")
        _validate_unique_mapping_values(self.claims, "candidate_claim_id", "candidate claim")
        return self


def load_claim_integrity_runtime_capture_manifest(path: Path) -> ClaimIntegrityRuntimeCaptureManifest:
    try:
        return ClaimIntegrityRuntimeCaptureManifest.model_validate_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid Claim Integrity runtime capture manifest: {path}") from exc


def fixture_fingerprint(dataset: BidBenchDataset) -> str:
    payload = json.dumps(
        dataset.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def capture_claim_integrity_runtime_candidate(
    db: Session,
    dataset: BidBenchDataset,
    manifest: ClaimIntegrityRuntimeCaptureManifest,
) -> BidBenchCandidate:
    """Build a structural BidBench candidate without exporting business text."""

    _validate_manifest(dataset, manifest)
    project = _load_project(db, manifest)
    execution_run = _load_execution_run(db, project, manifest)
    section_version = _load_section_version(db, project, execution_run, manifest)
    requirements = _load_project_requirements(db, project.id)
    claims = _load_run_claims(db, execution_run.id)
    _validate_execution_output(execution_run, section_version, claims)
    runtime_bridge = _validate_runtime_bridge(db, project, execution_run, manifest)

    requirement_maps = _exact_map(
        manifest.requirements,
        key="runtime_requirement_id",
        expected_ids={item.id for item in requirements},
        label="runtime requirement",
    )
    source_ids = {item.source_document_id for item in requirements if item.source_document_id}
    source_maps = _exact_map(
        manifest.source_documents,
        key="runtime_source_document_id",
        expected_ids=source_ids,
        label="runtime source document",
    )
    _validate_source_scope(db, project.id, source_ids)

    claim_ids = {claim.id for claim in claims}
    claim_maps = _exact_map(
        manifest.claims,
        key="runtime_claim_id",
        expected_ids=claim_ids,
        label="runtime claim",
    )
    _validate_claim_scope(claims, project.id, section_version.id, set(requirement_maps))

    evidence_ids = _referenced_evidence_ids(requirements, claims)
    evidence_maps = _exact_map(
        manifest.evidence,
        key="runtime_evidence_id",
        expected_ids=evidence_ids,
        label="runtime evidence",
    )
    _validate_evidence_scope(db, project.id, evidence_ids)

    requirements_by_truth_id = {item.id: item for item in dataset.requirements}
    source_ids_by_truth = {item.id for item in dataset.sources}
    evidence_ids_by_truth = {item.id for item in dataset.evidence}
    _validate_benchmark_mappings(
        manifest,
        requirement_ids=requirements_by_truth_id,
        source_ids=source_ids_by_truth,
        evidence_ids=evidence_ids_by_truth,
    )
    _validate_redacted_candidate_identifiers(
        manifest,
        {
            value
            for value in (
                project.id,
                project.org_id,
                execution_run.id,
                section_version.id,
                section_version.deliverable_section_id,
                runtime_bridge.id,
                runtime_bridge.org_id,
                runtime_bridge.user_id,
                runtime_bridge.project_id,
                runtime_bridge.execution_run_id,
            )
            if value
        }
        | {item.id for item in requirements}
        | source_ids
        | evidence_ids
        | claim_ids,
    )

    candidates = [
        _candidate_requirement(
            item,
            mapping=requirement_maps[item.id],
            truth=requirements_by_truth_id.get(requirement_maps[item.id].benchmark_requirement_id or ""),
            source_mapping=source_maps.get(item.source_document_id or ""),
            evidence_maps=evidence_maps,
        )
        for item in requirements
    ]
    candidate_claims = [
        _candidate_claim(
            claim,
            claim_mapping=claim_maps[claim.id],
            requirement_maps=requirement_maps,
            evidence_maps=evidence_maps,
        )
        for claim in claims
    ]
    return BidBenchCandidate(
        schema_version="1.0",
        dataset_id=dataset.dataset_id,
        candidate_id=manifest.candidate_id,
        system_name="bidpilot-claim-integrity-runtime",
        git_commit=manifest.git_commit,
        provider=manifest.provider,
        model=manifest.model,
        prompt_version=manifest.prompt_version,
        run_number=manifest.run_number,
        generated_at=datetime.now(UTC),
        latency_ms=manifest.latency_ms,
        estimated_cost_usd=manifest.estimated_cost_usd,
        provenance=manifest.provenance,
        requirements=candidates,
        claims=candidate_claims,
    )


def _validate_manifest(dataset: BidBenchDataset, manifest: ClaimIntegrityRuntimeCaptureManifest) -> None:
    if manifest.dataset_id != dataset.dataset_id:
        raise ValueError("claim capture manifest dataset_id does not match BidBench dataset")
    if manifest.fixture_fingerprint != fixture_fingerprint(dataset):
        raise ValueError("claim capture manifest fixture_fingerprint does not match BidBench dataset")
    if manifest.provenance.capture_kind != EvaluationCaptureKind.CURRENT_PIPELINE:
        raise ValueError("claim capture provenance must be current_pipeline")
    if manifest.provenance.review_level != EvaluationReviewLevel.TWO_PERSON_REVIEW:
        raise ValueError("claim capture provenance requires two_person_review")


def _load_project(db: Session, manifest: ClaimIntegrityRuntimeCaptureManifest) -> Project:
    project = db.get(Project, manifest.runtime_project_id)
    if project is None or project.status == "deleted":
        raise ValueError("claim capture project is unavailable")
    return project


def _load_execution_run(
    db: Session,
    project: Project,
    manifest: ClaimIntegrityRuntimeCaptureManifest,
) -> ExecutionRun:
    run = db.get(ExecutionRun, manifest.execution_run_id)
    if (
        run is None
        or run.project_id != project.id
        or run.run_type not in _DRAFT_RUN_TYPES
        or run.status != "succeeded"
    ):
        raise ValueError("claim capture execution provenance is invalid")
    return run


def _load_section_version(
    db: Session,
    project: Project,
    execution_run: ExecutionRun,
    manifest: ClaimIntegrityRuntimeCaptureManifest,
) -> SectionVersion:
    version = db.scalar(
        select(SectionVersion)
        .join(DeliverableSection, DeliverableSection.id == SectionVersion.deliverable_section_id)
        .join(Deliverable, Deliverable.id == DeliverableSection.deliverable_id)
        .where(
            SectionVersion.id == manifest.section_version_id,
            SectionVersion.generation_run_id == execution_run.id,
            Deliverable.project_id == project.id,
        )
    )
    if version is None:
        raise ValueError("claim capture section version provenance is invalid")
    return version


def _load_project_requirements(db: Session, project_id: str) -> list[RequirementItem]:
    return list(
        db.scalars(
            select(RequirementItem)
            .options(
                selectinload(RequirementItem.bid_profile),
                selectinload(RequirementItem.evidence_links),
            )
            .where(RequirementItem.project_id == project_id)
            .order_by(RequirementItem.id.asc())
        ).all()
    )


def _load_run_claims(
    db: Session,
    execution_run_id: str,
) -> list[Claim]:
    return list(
        db.scalars(
            select(Claim)
            .options(
                selectinload(Claim.requirement_links),
                selectinload(Claim.evidence_links),
            )
            .where(
                Claim.generation_run_id == execution_run_id,
            )
            .order_by(Claim.id.asc())
        ).all()
    )


def _validate_execution_output(
    execution_run: ExecutionRun,
    section_version: SectionVersion,
    claims: list[Claim],
) -> None:
    output = execution_run.output_json or {}
    if output.get("section_version_id") != section_version.id:
        raise ValueError("claim capture execution output does not retain the section version")
    claim_count = output.get("claim_count")
    if not isinstance(claim_count, int) or claim_count != len(claims):
        raise ValueError("claim capture execution output does not match persisted claims")
    integrity_status = output.get("claim_integrity_status")
    if not isinstance(integrity_status, str) or not integrity_status:
        raise ValueError("claim capture execution output has no integrity status")
    if claims and integrity_status != "proposed":
        raise ValueError("claim capture run has claims without proposed integrity status")


def _validate_runtime_bridge(
    db: Session,
    project: Project,
    execution_run: ExecutionRun,
    manifest: ClaimIntegrityRuntimeCaptureManifest,
) -> RuntimeRun:
    bridges = list(
        db.scalars(
            select(RuntimeRun)
            .where(RuntimeRun.execution_run_id == execution_run.id)
            .order_by(RuntimeRun.created_at.asc(), RuntimeRun.id.asc())
        ).all()
    )
    if len(bridges) != 1:
        raise ValueError("claim capture runtime bridge is ambiguous")
    bridge = bridges[0]
    if (
        bridge.kind != RuntimeRunKind.WORKFLOW_BRIDGE.value
        or bridge.status != RuntimeRunStatus.SUCCEEDED.value
        or bridge.org_id != project.org_id
        or bridge.project_id != project.id
    ):
        raise ValueError("claim capture runtime bridge scope is invalid")
    if manifest.model and bridge.model != manifest.model:
        raise ValueError("claim capture runtime bridge model does not match manifest")
    return bridge


def _exact_map(items: tuple, *, key: str, expected_ids: set[str], label: str) -> dict[str, object]:
    mapped = {getattr(item, key): item for item in items}
    if len(mapped) != len(items) or set(mapped) != expected_ids:
        raise ValueError(f"claim capture {label} map does not exactly cover the runtime scope")
    return mapped


def _validate_source_scope(db: Session, project_id: str, source_ids: set[str]) -> None:
    if not source_ids:
        return
    visible_ids = set(
        db.scalars(
            select(SourceDocument.id)
            .join(Bundle, Bundle.id == SourceDocument.bundle_id)
            .where(SourceDocument.id.in_(source_ids), Bundle.project_id == project_id)
        ).all()
    )
    if visible_ids != source_ids:
        raise ValueError("claim capture source-document scope is invalid")


def _validate_claim_scope(
    claims: list[Claim],
    project_id: str,
    section_version_id: str,
    project_requirement_ids: set[str],
) -> None:
    for claim in claims:
        linked_requirement_ids = {link.requirement_id for link in claim.requirement_links}
        if (
            claim.project_id != project_id
            or claim.section_version_id != section_version_id
            or claim.created_by_actor != "ai"
            or not linked_requirement_ids
            or not linked_requirement_ids.issubset(project_requirement_ids)
        ):
            raise ValueError("claim capture claim scope is invalid")


def _referenced_evidence_ids(requirements: list[RequirementItem], claims: list[Claim]) -> set[str]:
    return {
        evidence_id
        for requirement in requirements
        for link in requirement.evidence_links
        if link.relation_type == "supports"
        for evidence_id in (link.evidence_id,)
    } | {
        evidence_id
        for claim in claims
        for link in claim.evidence_links
        for evidence_id in (link.evidence_id,)
    }


def _validate_evidence_scope(db: Session, project_id: str, evidence_ids: set[str]) -> None:
    if not evidence_ids:
        return
    visible_ids = set(
        db.scalars(
            select(Evidence.id).where(Evidence.id.in_(evidence_ids), Evidence.project_id == project_id)
        ).all()
    )
    if visible_ids != evidence_ids:
        raise ValueError("claim capture evidence scope is invalid")


def _validate_benchmark_mappings(
    manifest: ClaimIntegrityRuntimeCaptureManifest,
    *,
    requirement_ids: dict[str, object],
    source_ids: set[str],
    evidence_ids: set[str],
) -> None:
    for item in manifest.requirements:
        if item.benchmark_requirement_id and item.benchmark_requirement_id not in requirement_ids:
            raise ValueError("claim capture requirement map references an unknown benchmark requirement")
    for item in manifest.source_documents:
        if item.benchmark_source_id and item.benchmark_source_id not in source_ids:
            raise ValueError("claim capture source map references an unknown benchmark source")
        if not item.benchmark_source_id and item.candidate_source_id in source_ids:
            raise ValueError("claim capture unmapped source id collides with a benchmark source")
    for item in manifest.evidence:
        if item.benchmark_evidence_id and item.benchmark_evidence_id not in evidence_ids:
            raise ValueError("claim capture evidence map references an unknown benchmark evidence")
        if not item.benchmark_evidence_id and item.candidate_evidence_id in evidence_ids:
            raise ValueError("claim capture unmapped evidence id collides with benchmark evidence")


def _validate_redacted_candidate_identifiers(
    manifest: ClaimIntegrityRuntimeCaptureManifest,
    runtime_ids: set[str],
) -> None:
    candidate_ids = {
        manifest.candidate_id,
        *(item.candidate_requirement_id for item in manifest.requirements),
        *(item.candidate_source_id for item in manifest.source_documents),
        *(item.candidate_evidence_id for item in manifest.evidence),
        *(item.candidate_claim_id for item in manifest.claims),
    }
    if candidate_ids & runtime_ids:
        raise ValueError("claim capture candidate identifiers must not reuse durable runtime IDs")


def _candidate_requirement(
    requirement: RequirementItem,
    *,
    mapping: ClaimIntegrityRuntimeRequirementMap,
    truth,
    source_mapping: ClaimIntegrityRuntimeSourceMap | None,
    evidence_maps: dict[str, ClaimIntegrityRuntimeEvidenceMap],
) -> BidBenchCandidateRequirement:
    text_matches_truth = bool(truth) and _normalize_text(requirement.requirement_text) == _normalize_text(
        truth.normalized_text
    )
    normalized_text = (
        truth.normalized_text
        if text_matches_truth
        else f"redacted-unmatched-{mapping.candidate_requirement_id}"
    )
    profile = requirement.bid_profile
    return BidBenchCandidateRequirement(
        id=mapping.candidate_requirement_id,
        normalized_text=normalized_text,
        requirement_type=_requirement_type(profile.bid_category if profile else "", requirement.priority, bool(profile and profile.is_mandatory)),
        is_mandatory=bool(profile and profile.is_mandatory) or requirement.priority in {"high", "critical"},
        coverage_status=_coverage_status(profile.coverage_status if profile else "uncovered", mapping.candidate_requirement_id),
        locators=_redacted_locators(requirement, truth, source_mapping, mapping.candidate_requirement_id),
        evidence_ids=sorted(
            {
                evidence_maps[link.evidence_id].candidate_evidence_id
                for link in requirement.evidence_links
                if link.relation_type == "supports"
            }
        ),
        confidence=requirement.extraction_confidence,
    )


def _candidate_claim(
    claim: Claim,
    *,
    claim_mapping: ClaimIntegrityRuntimeClaimMap,
    requirement_maps: dict[str, ClaimIntegrityRuntimeRequirementMap],
    evidence_maps: dict[str, ClaimIntegrityRuntimeEvidenceMap],
) -> BidBenchCandidateClaim:
    return BidBenchCandidateClaim(
        id=claim_mapping.candidate_claim_id,
        text=f"redacted-claim-{claim_mapping.candidate_claim_id}",
        requirement_ids=sorted(
            {requirement_maps[link.requirement_id].candidate_requirement_id for link in claim.requirement_links}
        ),
        evidence_ids=sorted(
            {evidence_maps[link.evidence_id].candidate_evidence_id for link in claim.evidence_links}
        ),
        is_inference=claim.claim_type.casefold() in {"inference", "inferred"},
        accepted=claim.status.casefold() in {"verified", "approved"},
    )


def _requirement_type(category: str, priority: str, is_mandatory: bool) -> RequirementType:
    try:
        return RequirementType(category.casefold())
    except ValueError:
        return RequirementType.MANDATORY if is_mandatory or priority.casefold() in {"high", "critical"} else RequirementType.TECHNICAL


def _coverage_status(value: str, candidate_requirement_id: str) -> CoverageStatus:
    try:
        return CoverageStatus(value.casefold())
    except ValueError as exc:
        raise ValueError(
            f"claim capture candidate requirement {candidate_requirement_id} has an invalid coverage status"
        ) from exc


def _redacted_locators(
    requirement: RequirementItem,
    truth,
    source_mapping: ClaimIntegrityRuntimeSourceMap | None,
    candidate_requirement_id: str,
) -> list[BidBenchLocator]:
    if truth is None or source_mapping is None or not source_mapping.benchmark_source_id:
        return []
    locator_json = requirement.source_locator_json
    if not isinstance(locator_json, dict):
        return []
    raw_locator = {
        "source_id": source_mapping.candidate_source_id,
        **{
            field: locator_json[field]
            for field in ("page", "section", "table", "text_anchor", "bbox")
            if field in locator_json
        },
    }
    try:
        observed_locator = BidBenchLocator.model_validate(raw_locator)
    except ValueError as exc:
        raise ValueError(
            f"claim capture candidate requirement {candidate_requirement_id} has an invalid locator"
        ) from exc
    return [locator for locator in truth.locators if _locator_matches(observed_locator, locator)]


def _validate_unique_mapping_values(items: tuple, attribute: str, label: str) -> None:
    values = [getattr(item, attribute) for item in items]
    if len(values) != len(set(values)):
        raise ValueError(f"claim capture manifest has duplicate {label} mappings")


__all__ = [
    "ClaimIntegrityRuntimeCaptureManifest",
    "ClaimIntegrityRuntimeClaimMap",
    "ClaimIntegrityRuntimeEvidenceMap",
    "ClaimIntegrityRuntimeRequirementMap",
    "ClaimIntegrityRuntimeSourceMap",
    "capture_claim_integrity_runtime_candidate",
    "fixture_fingerprint",
    "load_claim_integrity_runtime_capture_manifest",
]
