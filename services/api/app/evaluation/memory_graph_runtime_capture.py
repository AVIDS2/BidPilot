"""Build redacted MemoryGraphBench captures from reviewed workflow records.

The private manifest maps benchmark cases to database rows. It is deliberately
never included in the generated evaluation run, which contains only the
synthetic/public identifiers from the frozen benchmark dataset.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ExecutionRun,
    MemoryEvidenceLink,
    MemoryGraphReviewDecision,
    MemoryRecord,
    RuntimeRun,
)
from contracts import (
    EvaluationEvidenceProvenance,
    MemoryCitation,
    MemoryCitationSource,
    MemoryKind,
    MemoryGraphProposal,
    MemoryScope,
    MemoryStatus,
    RuntimeRunKind,
    RuntimeRunStatus,
    memory_graph_item_id,
    memory_graph_proposal_fingerprint,
    memory_graph_source_snapshot_fingerprint,
)

from .memory_graph_metrics import (
    MemoryGraphBenchmarkCase,
    MemoryGraphBenchmarkDataset,
    MemoryGraphCandidateObservation,
    MemoryGraphEvaluationRun,
    MemoryGraphReviewSummary,
    fixture_fingerprint,
)


class _MemoryGraphRuntimeCaptureModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class MemoryGraphRuntimeEvidenceMap(_MemoryGraphRuntimeCaptureModel):
    """Private mapping from durable source references to benchmark references."""

    runtime_source_type: MemoryCitationSource
    runtime_source_id: str = Field(min_length=1, max_length=100)
    benchmark_source_type: MemoryCitationSource
    benchmark_source_id: str = Field(min_length=1, max_length=100)

    @property
    def runtime_key(self) -> tuple[str, str]:
        return (self.runtime_source_type.value, self.runtime_source_id)

    @property
    def benchmark_key(self) -> tuple[str, str]:
        return (self.benchmark_source_type.value, self.benchmark_source_id)


class MemoryGraphRuntimeCaptureItem(_MemoryGraphRuntimeCaptureModel):
    """Private database mapping for one benchmark case."""

    case_id: str = Field(min_length=1, max_length=100)
    proposal_memory_record_id: str = Field(min_length=1, max_length=100)
    source_memory_record_id: str = Field(min_length=1, max_length=100)
    execution_run_id: str = Field(min_length=1, max_length=100)
    evidence_map: tuple[MemoryGraphRuntimeEvidenceMap, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_evidence_map(self) -> MemoryGraphRuntimeCaptureItem:
        runtime_keys = [item.runtime_key for item in self.evidence_map]
        benchmark_keys = [item.benchmark_key for item in self.evidence_map]
        if len(runtime_keys) != len(set(runtime_keys)):
            raise ValueError("memory graph runtime capture evidence map has duplicate runtime references")
        if len(benchmark_keys) != len(set(benchmark_keys)):
            raise ValueError("memory graph runtime capture evidence map has duplicate benchmark references")
        return self


class MemoryGraphRuntimeCaptureManifest(_MemoryGraphRuntimeCaptureModel):
    """Private manifest used to build one redacted graph benchmark candidate."""

    schema_version: Literal["1.0"] = "1.0"
    dataset_id: str = Field(min_length=1, max_length=100)
    fixture_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    extractor_policy_version: str = Field(min_length=1, max_length=100)
    captures: tuple[MemoryGraphRuntimeCaptureItem, ...] = Field(min_length=1)
    git_commit: str | None = Field(default=None, max_length=100)
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=255)
    latency_ms: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    provenance: EvaluationEvidenceProvenance | None = None

    @model_validator(mode="after")
    def validate_capture_ids(self) -> MemoryGraphRuntimeCaptureManifest:
        case_ids = [item.case_id for item in self.captures]
        proposal_ids = [item.proposal_memory_record_id for item in self.captures]
        execution_run_ids = [item.execution_run_id for item in self.captures]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("memory graph runtime capture manifest contains duplicate case ids")
        if len(proposal_ids) != len(set(proposal_ids)):
            raise ValueError("memory graph runtime capture manifest cannot reuse a proposal record")
        if len(execution_run_ids) != len(set(execution_run_ids)):
            raise ValueError("memory graph runtime capture manifest cannot reuse an execution run")
        return self


def load_memory_graph_runtime_capture_manifest(path: Path) -> MemoryGraphRuntimeCaptureManifest:
    try:
        return MemoryGraphRuntimeCaptureManifest.model_validate_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid MemoryGraphBench runtime capture manifest: {path}") from exc


def capture_memory_graph_runtime_run(
    db: Session,
    dataset: MemoryGraphBenchmarkDataset,
    manifest: MemoryGraphRuntimeCaptureManifest,
) -> MemoryGraphEvaluationRun:
    """Export reviewed, source-current graph proposals without durable IDs or text."""
    expected_fingerprint = fixture_fingerprint(dataset)
    if manifest.dataset_id != dataset.dataset_id:
        raise ValueError("memory graph runtime capture manifest dataset_id does not match benchmark dataset")
    if manifest.fixture_fingerprint != expected_fingerprint:
        raise ValueError("memory graph runtime capture manifest fixture_fingerprint does not match benchmark dataset")

    cases = {case.id: case for case in dataset.cases}
    captures = {item.case_id: item for item in manifest.captures}
    if set(captures) != set(cases):
        raise ValueError("memory graph runtime capture manifest must map every benchmark case exactly once")

    observations = tuple(
        _capture_observation(
            db,
            case=case,
            capture=captures[case.id],
            manifest=manifest,
        )
        for case in dataset.cases
    )
    return MemoryGraphEvaluationRun(
        dataset_id=dataset.dataset_id,
        fixture_fingerprint=expected_fingerprint,
        extractor_policy_version=manifest.extractor_policy_version,
        results=observations,
        git_commit=manifest.git_commit,
        provider=manifest.provider,
        model=manifest.model,
        latency_ms=manifest.latency_ms,
        estimated_cost_usd=manifest.estimated_cost_usd,
        provenance=manifest.provenance,
    )


def _capture_observation(
    db: Session,
    *,
    case: MemoryGraphBenchmarkCase,
    capture: MemoryGraphRuntimeCaptureItem,
    manifest: MemoryGraphRuntimeCaptureManifest,
) -> MemoryGraphCandidateObservation:
    proposal_record = db.get(MemoryRecord, capture.proposal_memory_record_id)
    source_record = db.get(MemoryRecord, capture.source_memory_record_id)
    if proposal_record is None or source_record is None:
        raise ValueError(f"memory graph runtime capture case {case.id} has an unavailable record")
    if not _is_active_shared_source(source_record):
        raise ValueError(f"memory graph runtime capture case {case.id} source is not active shared memory")
    if (
        proposal_record.org_id != source_record.org_id
        or proposal_record.project_id != source_record.project_id
        or proposal_record.scope != MemoryScope.PROJECT_SHARED.value
        or proposal_record.kind != MemoryKind.ENTITY_NOTE.value
        or proposal_record.status not in {MemoryStatus.PROPOSED.value, MemoryStatus.ACTIVE.value}
        or proposal_record.deleted_at is not None
        or (proposal_record.expires_at is not None and proposal_record.expires_at <= _utc_naive_now())
    ):
        raise ValueError(f"memory graph runtime capture case {case.id} proposal scope is invalid")

    structured_data = proposal_record.structured_data_json or {}
    if structured_data.get("source_memory_record_id") != source_record.id:
        raise ValueError(f"memory graph runtime capture case {case.id} proposal/source linkage is invalid")
    if structured_data.get("graph_policy_version") != manifest.extractor_policy_version:
        raise ValueError(f"memory graph runtime capture case {case.id} policy version does not match")

    proposal = _load_proposal(proposal_record, case_id=case.id)
    source_citations = _load_citations(db, source_record.id)
    try:
        proposal.validate_evidence_sources({(citation.source_type.value, citation.source_id) for citation in source_citations})
    except ValueError as exc:
        raise ValueError(f"memory graph runtime capture case {case.id} proposal evidence is invalid") from exc
    expected_snapshot = memory_graph_source_snapshot_fingerprint(
        policy_version=manifest.extractor_policy_version,
        memory_record_id=source_record.id,
        title=source_record.title,
        body_markdown=source_record.body_markdown,
        citations=source_citations,
    )
    if proposal_record.content_fingerprint != expected_snapshot:
        raise ValueError(f"memory graph runtime capture case {case.id} source snapshot is stale")

    _validate_execution_provenance(
        db,
        case_id=case.id,
        capture=capture,
        manifest=manifest,
        source_record=source_record,
        proposal_record=proposal_record,
        expected_snapshot=expected_snapshot,
    )
    review_summary = _review_summary(
        db,
        proposal_record=proposal_record,
        proposal=proposal,
        case_id=case.id,
    )
    if proposal_record.status == MemoryStatus.ACTIVE.value and review_summary.pending_item_count:
        raise ValueError(f"memory graph runtime capture case {case.id} active proposal has pending review")

    evidence_mapping = {item.runtime_key: item.benchmark_key for item in capture.evidence_map}
    proposal_evidence = _proposal_evidence_keys(proposal)
    if set(evidence_mapping) != proposal_evidence:
        raise ValueError(f"memory graph runtime capture case {case.id} evidence map must exactly cover proposal evidence")
    available_benchmark_evidence = {(item.source_type.value, item.source_id) for item in case.available_evidence_refs}
    if not set(evidence_mapping.values()).issubset(available_benchmark_evidence):
        raise ValueError(f"memory graph runtime capture case {case.id} maps evidence outside the benchmark case")

    return MemoryGraphCandidateObservation(
        case_id=case.id,
        org_id=case.org_id,
        project_id=case.project_id,
        memory_record_id=case.memory_record_id,
        proposal_json=_redact_proposal_evidence(proposal, evidence_mapping),
        review_summary=review_summary,
    )


def _is_active_shared_source(record: MemoryRecord) -> bool:
    now = _utc_naive_now()
    return bool(
        record.project_id
        and record.scope == MemoryScope.PROJECT_SHARED.value
        and record.status == MemoryStatus.ACTIVE.value
        and record.deleted_at is None
        and (record.expires_at is None or record.expires_at > now)
    )


def _utc_naive_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _load_proposal(record: MemoryRecord, *, case_id: str) -> MemoryGraphProposal:
    candidate = (record.structured_data_json or {}).get("memory_graph_proposal")
    if not isinstance(candidate, dict):
        raise ValueError(f"memory graph runtime capture case {case_id} has no graph proposal")
    try:
        return MemoryGraphProposal.model_validate(candidate)
    except ValueError as exc:
        raise ValueError(f"memory graph runtime capture case {case_id} graph proposal is invalid") from exc


def _load_citations(db: Session, memory_record_id: str) -> tuple[MemoryCitation, ...]:
    links = list(
        db.scalars(
            select(MemoryEvidenceLink)
            .where(MemoryEvidenceLink.memory_record_id == memory_record_id)
            .order_by(MemoryEvidenceLink.id.asc())
        ).all()
    )
    return tuple(
        MemoryCitation(
            source_type=link.source_type,
            source_id=link.source_id,
            label=link.label,
            locator_json=link.locator_json,
        )
        for link in links
    )


def _validate_execution_provenance(
    db: Session,
    *,
    case_id: str,
    capture: MemoryGraphRuntimeCaptureItem,
    manifest: MemoryGraphRuntimeCaptureManifest,
    source_record: MemoryRecord,
    proposal_record: MemoryRecord,
    expected_snapshot: str,
) -> None:
    execution_run = db.get(ExecutionRun, capture.execution_run_id)
    if (
        execution_run is None
        or execution_run.project_id != source_record.project_id
        or execution_run.run_type != "memory_graph_extraction"
        or execution_run.status != "succeeded"
    ):
        raise ValueError(f"memory graph runtime capture case {case_id} execution provenance is invalid")
    input_json = execution_run.input_json or {}
    output_json = execution_run.output_json or {}
    if (
        input_json.get("memory_record_id") != source_record.id
        or input_json.get("source_snapshot_fingerprint") != expected_snapshot
        or input_json.get("graph_policy_version") != manifest.extractor_policy_version
        or output_json.get("proposal_memory_id") != proposal_record.id
    ):
        raise ValueError(f"memory graph runtime capture case {case_id} execution snapshot is invalid")

    runtime_runs = list(
        db.scalars(
            select(RuntimeRun)
            .where(RuntimeRun.execution_run_id == execution_run.id)
            .order_by(RuntimeRun.created_at.asc(), RuntimeRun.id.asc())
        ).all()
    )
    if len(runtime_runs) != 1:
        raise ValueError(f"memory graph runtime capture case {case_id} runtime bridge is ambiguous")
    runtime_run = runtime_runs[0]
    if (
        runtime_run.kind != RuntimeRunKind.WORKFLOW_BRIDGE.value
        or runtime_run.status != RuntimeRunStatus.SUCCEEDED.value
        or runtime_run.org_id != source_record.org_id
        or runtime_run.project_id != source_record.project_id
    ):
        raise ValueError(f"memory graph runtime capture case {case_id} runtime bridge scope is invalid")
    if manifest.model and runtime_run.model != manifest.model:
        raise ValueError(f"memory graph runtime capture case {case_id} model does not match the manifest")


def _review_summary(
    db: Session,
    *,
    proposal_record: MemoryRecord,
    proposal: MemoryGraphProposal,
    case_id: str,
) -> MemoryGraphReviewSummary:
    proposal_fingerprint = memory_graph_proposal_fingerprint(proposal)
    item_types = _proposal_item_types(proposal, proposal_fingerprint)
    decisions = list(
        db.scalars(
            select(MemoryGraphReviewDecision)
            .where(
                MemoryGraphReviewDecision.proposal_memory_record_id == proposal_record.id,
                MemoryGraphReviewDecision.proposal_fingerprint == proposal_fingerprint,
            )
            .order_by(MemoryGraphReviewDecision.item_id.asc())
        ).all()
    )
    seen_item_ids: set[str] = set()
    accepted = 0
    rejected = 0
    for decision in decisions:
        expected_item_type = item_types.get(decision.item_id)
        if (
            expected_item_type is None
            or decision.item_type != expected_item_type
            or decision.org_id != proposal_record.org_id
            or decision.project_id != proposal_record.project_id
            or decision.item_id in seen_item_ids
            or decision.decision not in {"accepted", "rejected"}
        ):
            raise ValueError(f"memory graph runtime capture case {case_id} review ledger is invalid")
        seen_item_ids.add(decision.item_id)
        if decision.decision == "accepted":
            accepted += 1
        else:
            rejected += 1
    return MemoryGraphReviewSummary(
        accepted_item_count=accepted,
        rejected_item_count=rejected,
        pending_item_count=len(item_types) - len(seen_item_ids),
    )


def _proposal_item_types(proposal: MemoryGraphProposal, proposal_fingerprint: str) -> dict[str, Literal["entity", "relation"]]:
    item_types: dict[str, Literal["entity", "relation"]] = {
        memory_graph_item_id(proposal_fingerprint, "entity", entity.semantic_key): "entity"
        for entity in proposal.entities
    }
    entity_names = {entity.local_id: entity.canonical_name for entity in proposal.entities}
    item_types.update(
        {
            memory_graph_item_id(
                proposal_fingerprint,
                "relation",
                (
                    entity_names[relation.subject_local_id],
                    relation.predicate.value,
                    entity_names[relation.object_local_id],
                ),
            ): "relation"
            for relation in proposal.relations
        }
    )
    return item_types


def _proposal_evidence_keys(proposal: MemoryGraphProposal) -> set[tuple[str, str]]:
    return {
        evidence_ref.key
        for item in (*proposal.entities, *proposal.relations)
        for evidence_ref in item.evidence_refs
    }


def _redact_proposal_evidence(
    proposal: MemoryGraphProposal,
    evidence_mapping: dict[tuple[str, str], tuple[str, str]],
) -> dict[str, object]:
    """Replace durable evidence references while retaining typed graph semantics."""
    payload = proposal.model_dump(mode="json")
    for item_type in ("entities", "relations"):
        for item in payload[item_type]:
            for evidence_ref in item["evidence_refs"]:
                mapped = evidence_mapping[(str(evidence_ref["source_type"]), str(evidence_ref["source_id"]))]
                evidence_ref["source_type"], evidence_ref["source_id"] = mapped
    return payload


__all__ = [
    "MemoryGraphRuntimeCaptureItem",
    "MemoryGraphRuntimeCaptureManifest",
    "MemoryGraphRuntimeEvidenceMap",
    "capture_memory_graph_runtime_run",
    "load_memory_graph_runtime_capture_manifest",
]
