"""Offline quality metrics for reviewed Bid Wiki graph proposals.

The evaluator consumes synthetic or controlled captures. It never reads a
customer document, invokes a model, or persists graph output. That keeps graph
quality measurable before entity/relation materialization is enabled.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts import (
    EvaluationCaptureKind,
    EvaluationEvidenceProvenance,
    EvaluationReviewLevel,
    MemoryGraphEvidenceRef,
    MemoryGraphEntityType,
    MemoryGraphProposal,
    MemoryGraphRelationPredicate,
    normalize_memory_graph_name,
)


class _EvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class MemoryGraphBenchmarkEntity(_EvaluationModel):
    canonical_name: str = Field(min_length=1, max_length=240)
    entity_type: MemoryGraphEntityType

    @property
    def semantic_key(self) -> tuple[str, str]:
        return (self.entity_type.value, normalize_memory_graph_name(self.canonical_name))


class MemoryGraphBenchmarkRelation(_EvaluationModel):
    subject: MemoryGraphBenchmarkEntity
    predicate: MemoryGraphRelationPredicate
    object: MemoryGraphBenchmarkEntity
    expected_evidence_refs: tuple[MemoryGraphEvidenceRef, ...] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def validate_source_ids(self) -> MemoryGraphBenchmarkRelation:
        if len(_evidence_ref_keys(self.expected_evidence_refs)) != len(self.expected_evidence_refs):
            raise ValueError("memory graph benchmark relation evidence refs must be unique")
        return self

    @property
    def semantic_key(self) -> tuple[tuple[str, str], str, tuple[str, str]]:
        return (self.subject.semantic_key, self.predicate.value, self.object.semantic_key)


class MemoryGraphBenchmarkCase(_EvaluationModel):
    id: str = Field(min_length=1, max_length=100)
    org_id: str = Field(min_length=1, max_length=100)
    project_id: str = Field(min_length=1, max_length=100)
    memory_record_id: str = Field(min_length=1, max_length=100)
    available_evidence_refs: tuple[MemoryGraphEvidenceRef, ...] = Field(min_length=1, max_length=32)
    expected_entities: tuple[MemoryGraphBenchmarkEntity, ...] = Field(min_length=1, max_length=24)
    expected_relations: tuple[MemoryGraphBenchmarkRelation, ...] = Field(default=(), max_length=48)

    @model_validator(mode="after")
    def validate_case(self) -> MemoryGraphBenchmarkCase:
        evidence_refs = _evidence_ref_keys(self.available_evidence_refs)
        if len(evidence_refs) != len(self.available_evidence_refs):
            raise ValueError("memory graph benchmark evidence refs must be unique")

        entity_keys = [entity.semantic_key for entity in self.expected_entities]
        if len(entity_keys) != len(set(entity_keys)):
            raise ValueError("memory graph benchmark entities must be unique")

        relation_keys = [relation.semantic_key for relation in self.expected_relations]
        if len(relation_keys) != len(set(relation_keys)):
            raise ValueError("memory graph benchmark relations must be unique")
        known_entities = set(entity_keys)
        for relation in self.expected_relations:
            if relation.subject.semantic_key not in known_entities or relation.object.semantic_key not in known_entities:
                raise ValueError("memory graph benchmark relations must reference expected entities")
            if _evidence_ref_keys(relation.expected_evidence_refs) - evidence_refs:
                raise ValueError("memory graph benchmark relation uses unavailable evidence")
        return self


class MemoryGraphBenchmarkDataset(_EvaluationModel):
    schema_version: str = "1.0"
    dataset_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    dataset_role: str = Field(min_length=1, max_length=30)
    description: str | None = Field(default=None, max_length=4_000)
    cases: tuple[MemoryGraphBenchmarkCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_case_ids(self) -> MemoryGraphBenchmarkDataset:
        case_ids = [case.id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("memory graph benchmark cases contain duplicate ids")
        return self


class MemoryGraphCandidateObservation(_EvaluationModel):
    """A redacted capture of one extractor result, not model reasoning."""

    case_id: str = Field(min_length=1, max_length=100)
    org_id: str = Field(min_length=1, max_length=100)
    project_id: str = Field(min_length=1, max_length=100)
    memory_record_id: str = Field(min_length=1, max_length=100)
    proposal_json: Any | None = None
    error_code: str | None = Field(default=None, max_length=100)
    review_summary: "MemoryGraphReviewSummary | None" = None

    @model_validator(mode="after")
    def validate_outcome(self) -> MemoryGraphCandidateObservation:
        if (self.proposal_json is None) == (self.error_code is None):
            raise ValueError("memory graph observation requires exactly one proposal or error code")
        if self.review_summary is not None and self.proposal_json is None:
            raise ValueError("memory graph review summary requires a proposal result")
        return self


class MemoryGraphReviewSummary(_EvaluationModel):
    """Redacted outcome counts from the durable per-item review ledger."""

    accepted_item_count: int = Field(ge=0)
    rejected_item_count: int = Field(ge=0)
    pending_item_count: int = Field(default=0, ge=0)

    @property
    def reviewed_item_count(self) -> int:
        return self.accepted_item_count + self.rejected_item_count

    @property
    def observed_item_count(self) -> int:
        return self.reviewed_item_count + self.pending_item_count


class MemoryGraphEvaluationRun(_EvaluationModel):
    schema_version: str = "1.0"
    dataset_id: str = Field(min_length=1, max_length=100)
    fixture_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    extractor_policy_version: str = Field(min_length=1, max_length=100)
    results: tuple[MemoryGraphCandidateObservation, ...] = Field(min_length=1)
    git_commit: str | None = Field(default=None, max_length=100)
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=255)
    latency_ms: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    provenance: EvaluationEvidenceProvenance | None = None

    @model_validator(mode="after")
    def validate_unique_case_results(self) -> MemoryGraphEvaluationRun:
        case_ids = [result.case_id for result in self.results]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("memory graph evaluation run contains duplicate case results")
        return self


class MemoryGraphMetricCounts(_EvaluationModel):
    case_count: int = Field(ge=0)
    schema_valid_case_count: int = Field(ge=0)
    scope_valid_case_count: int = Field(ge=0)
    expected_entity_count: int = Field(ge=0)
    candidate_entity_count: int = Field(ge=0)
    matched_entity_count: int = Field(ge=0)
    expected_relation_count: int = Field(ge=0)
    candidate_relation_count: int = Field(ge=0)
    matched_relation_count: int = Field(ge=0)
    graph_item_count: int = Field(ge=0)
    evidence_valid_item_count: int = Field(ge=0)
    expected_relation_grounding_count: int = Field(ge=0)
    grounded_relation_hit_count: int = Field(ge=0)
    review_summary_case_count: int = Field(ge=0)
    review_summary_valid_case_count: int = Field(ge=0)
    reviewed_graph_item_count: int = Field(ge=0)
    observed_graph_item_count: int = Field(ge=0)
    fully_reviewed_case_count: int = Field(ge=0)


class MemoryGraphMetrics(_EvaluationModel):
    formula_version: str = "1.0"
    counts: MemoryGraphMetricCounts
    schema_validity_rate: float = Field(ge=0, le=1)
    scope_isolation_pass_rate: float = Field(ge=0, le=1)
    entity_precision: float = Field(ge=0, le=1)
    entity_recall: float = Field(ge=0, le=1)
    relation_precision: float = Field(ge=0, le=1)
    relation_recall: float = Field(ge=0, le=1)
    evidence_validity_rate: float = Field(ge=0, le=1)
    grounded_relation_recall: float = Field(ge=0, le=1)
    review_summary_validity_rate: float | None = Field(default=None, ge=0, le=1)
    review_decision_coverage_rate: float | None = Field(default=None, ge=0, le=1)
    full_review_completion_rate: float | None = Field(default=None, ge=0, le=1)


class MemoryGraphCaptureReadiness(_EvaluationModel):
    """Whether a capture can establish a baseline, never a release verdict."""

    controlled_capture_ready: bool
    failures: tuple[str, ...] = ()


class MemoryGraphEvaluationReport(_EvaluationModel):
    schema_version: str = "1.0"
    generated_at: datetime
    dataset_id: str
    dataset_role: str
    fixture_fingerprint: str
    extractor_policy_version: str
    git_commit: str | None = None
    provider: str | None = None
    model: str | None = None
    latency_ms: int | None = None
    estimated_cost_usd: float | None = None
    provenance: EvaluationEvidenceProvenance | None = None
    metrics: MemoryGraphMetrics
    capture_readiness: MemoryGraphCaptureReadiness


def fixture_fingerprint(dataset: MemoryGraphBenchmarkDataset) -> str:
    payload = json.dumps(
        dataset.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_memory_graph_benchmark_dataset(path: Path) -> MemoryGraphBenchmarkDataset:
    try:
        return MemoryGraphBenchmarkDataset.model_validate_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid memory graph benchmark dataset: {path}") from exc


def load_memory_graph_evaluation_run(path: Path) -> MemoryGraphEvaluationRun:
    try:
        return MemoryGraphEvaluationRun.model_validate_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid memory graph evaluation run: {path}") from exc


def score_memory_graph_run(
    dataset: MemoryGraphBenchmarkDataset,
    run: MemoryGraphEvaluationRun,
) -> MemoryGraphEvaluationReport:
    """Score a captured proposal run without invoking models or databases."""
    if run.dataset_id != dataset.dataset_id:
        raise ValueError("memory graph run dataset_id does not match benchmark dataset")
    expected_fingerprint = fixture_fingerprint(dataset)
    if run.fixture_fingerprint != expected_fingerprint:
        raise ValueError("memory graph run fixture_fingerprint does not match benchmark dataset")
    if len(run.results) != len(dataset.cases):
        raise ValueError("memory graph run must contain exactly one result for each benchmark case")

    results_by_case = {result.case_id: result for result in run.results}
    if set(results_by_case) != {case.id for case in dataset.cases}:
        raise ValueError("memory graph run case ids do not match benchmark dataset")

    counts = {
        "case_count": len(dataset.cases),
        "schema_valid_case_count": 0,
        "scope_valid_case_count": 0,
        "expected_entity_count": 0,
        "candidate_entity_count": 0,
        "matched_entity_count": 0,
        "expected_relation_count": 0,
        "candidate_relation_count": 0,
        "matched_relation_count": 0,
        "graph_item_count": 0,
        "evidence_valid_item_count": 0,
        "expected_relation_grounding_count": 0,
        "grounded_relation_hit_count": 0,
        "review_summary_case_count": 0,
        "review_summary_valid_case_count": 0,
        "reviewed_graph_item_count": 0,
        "observed_graph_item_count": 0,
        "fully_reviewed_case_count": 0,
    }

    for case in dataset.cases:
        result = results_by_case[case.id]
        counts["expected_entity_count"] += len(case.expected_entities)
        counts["expected_relation_count"] += len(case.expected_relations)
        counts["expected_relation_grounding_count"] += len(case.expected_relations)

        if not _matches_case_scope(case, result):
            continue
        counts["scope_valid_case_count"] += 1
        proposal = _parse_proposal(result)
        if proposal is None:
            continue
        counts["schema_valid_case_count"] += 1

        available_evidence_refs = _evidence_ref_keys(case.available_evidence_refs)
        entity_keys_by_local_id = {entity.local_id: entity.semantic_key for entity in proposal.entities}
        candidate_entity_keys = set(entity_keys_by_local_id.values())
        expected_entity_keys = {entity.semantic_key for entity in case.expected_entities}
        counts["candidate_entity_count"] += len(proposal.entities)
        counts["matched_entity_count"] += len(candidate_entity_keys & expected_entity_keys)

        relation_items = [
            (
                (entity_keys_by_local_id[relation.subject_local_id], relation.predicate.value, entity_keys_by_local_id[relation.object_local_id]),
                relation.evidence_refs,
            )
            for relation in proposal.relations
        ]
        candidate_relation_keys = {item[0] for item in relation_items}
        expected_relations = {relation.semantic_key: relation for relation in case.expected_relations}
        counts["candidate_relation_count"] += len(relation_items)
        counts["matched_relation_count"] += len(candidate_relation_keys & set(expected_relations))

        for entity in proposal.entities:
            counts["graph_item_count"] += 1
            if _evidence_ref_keys(entity.evidence_refs).issubset(available_evidence_refs):
                counts["evidence_valid_item_count"] += 1
        for relation_key, evidence_refs in relation_items:
            counts["graph_item_count"] += 1
            evidence_is_valid = _evidence_ref_keys(evidence_refs).issubset(available_evidence_refs)
            if evidence_is_valid:
                counts["evidence_valid_item_count"] += 1
            expected = expected_relations.get(relation_key)
            if (
                expected is not None
                and evidence_is_valid
                and _evidence_ref_keys(evidence_refs) & _evidence_ref_keys(expected.expected_evidence_refs)
            ):
                counts["grounded_relation_hit_count"] += 1

        review_summary = result.review_summary
        if review_summary is not None:
            counts["review_summary_case_count"] += 1
            graph_item_count = len(proposal.entities) + len(proposal.relations)
            if review_summary.observed_item_count == graph_item_count:
                counts["review_summary_valid_case_count"] += 1
                counts["reviewed_graph_item_count"] += review_summary.reviewed_item_count
                counts["observed_graph_item_count"] += graph_item_count
                if review_summary.pending_item_count == 0:
                    counts["fully_reviewed_case_count"] += 1

    metric_counts = MemoryGraphMetricCounts(**counts)
    metrics = MemoryGraphMetrics(
        counts=metric_counts,
        schema_validity_rate=_ratio(metric_counts.schema_valid_case_count, metric_counts.case_count),
        scope_isolation_pass_rate=_ratio(metric_counts.scope_valid_case_count, metric_counts.case_count),
        entity_precision=_ratio(metric_counts.matched_entity_count, metric_counts.candidate_entity_count),
        entity_recall=_ratio(metric_counts.matched_entity_count, metric_counts.expected_entity_count),
        relation_precision=_ratio(metric_counts.matched_relation_count, metric_counts.candidate_relation_count),
        relation_recall=_ratio(metric_counts.matched_relation_count, metric_counts.expected_relation_count),
        evidence_validity_rate=_ratio(metric_counts.evidence_valid_item_count, metric_counts.graph_item_count),
        grounded_relation_recall=_ratio(
            metric_counts.grounded_relation_hit_count,
            metric_counts.expected_relation_grounding_count,
        ),
        review_summary_validity_rate=(
            _ratio(metric_counts.review_summary_valid_case_count, metric_counts.review_summary_case_count)
            if metric_counts.review_summary_case_count
            else None
        ),
        review_decision_coverage_rate=(
            _ratio(metric_counts.reviewed_graph_item_count, metric_counts.observed_graph_item_count)
            if metric_counts.observed_graph_item_count
            else None
        ),
        full_review_completion_rate=(
            _ratio(metric_counts.fully_reviewed_case_count, metric_counts.review_summary_valid_case_count)
            if metric_counts.review_summary_valid_case_count
            else None
        ),
    )
    capture_readiness = evaluate_memory_graph_capture_readiness(run, metrics)
    return MemoryGraphEvaluationReport(
        generated_at=datetime.now(UTC),
        dataset_id=dataset.dataset_id,
        dataset_role=dataset.dataset_role,
        fixture_fingerprint=expected_fingerprint,
        extractor_policy_version=run.extractor_policy_version,
        git_commit=run.git_commit,
        provider=run.provider,
        model=run.model,
        latency_ms=run.latency_ms,
        estimated_cost_usd=run.estimated_cost_usd,
        provenance=run.provenance,
        metrics=metrics,
        capture_readiness=capture_readiness,
    )


def evaluate_memory_graph_capture_readiness(
    run: MemoryGraphEvaluationRun,
    metrics: MemoryGraphMetrics,
) -> MemoryGraphCaptureReadiness:
    """Check capture integrity before it is used to establish quality baselines.

    This deliberately has no precision/recall threshold. Those values must be
    learned from reviewed regression data before they are promoted into a
    materialization or release policy.
    """
    failures: list[str] = []
    if not run.git_commit:
        failures.append("git_commit is required for a controlled capture")
    if not run.provider:
        failures.append("provider is required for a controlled capture")
    if not run.model:
        failures.append("model is required for a controlled capture")
    if run.provenance is None:
        failures.append("provenance is required for a controlled capture")
    else:
        if run.provenance.capture_kind is EvaluationCaptureKind.CONTROL_FIXTURE:
            failures.append("control_fixture captures cannot establish a quality baseline")
        if run.provenance.review_level is EvaluationReviewLevel.UNREVIEWED:
            failures.append("reviewed capture metadata is required")

    required_metrics = (
        ("schema_validity_rate", metrics.schema_validity_rate),
        ("scope_isolation_pass_rate", metrics.scope_isolation_pass_rate),
        ("evidence_validity_rate", metrics.evidence_validity_rate),
    )
    for name, value in required_metrics:
        if value != 1:
            failures.append(f"{name}={value:.4f} must equal 1.0000 for a controlled capture")
    if metrics.review_summary_validity_rate != 1:
        failures.append("every successful proposal requires a valid reviewer summary")
    if metrics.review_decision_coverage_rate != 1:
        failures.append("every proposed graph item must have a reviewer decision")
    if metrics.full_review_completion_rate != 1:
        failures.append("every captured proposal must have a completed review")
    return MemoryGraphCaptureReadiness(
        controlled_capture_ready=not failures,
        failures=tuple(failures),
    )


def render_memory_graph_markdown(report: MemoryGraphEvaluationReport) -> str:
    metrics = report.metrics
    lines = [
        "# MemoryGraphBench Report",
        "",
        f"- Dataset: `{report.dataset_id}` ({report.dataset_role})",
        f"- Extractor policy: `{report.extractor_policy_version}`",
        f"- Provider/model: `{report.provider or 'not recorded'}` / `{report.model or 'not recorded'}`",
        f"- Schema validity: {metrics.schema_validity_rate:.1%}",
        f"- Scope isolation: {metrics.scope_isolation_pass_rate:.1%}",
        f"- Entity precision / recall: {metrics.entity_precision:.1%} / {metrics.entity_recall:.1%}",
        f"- Relation precision / recall: {metrics.relation_precision:.1%} / {metrics.relation_recall:.1%}",
        f"- Evidence validity: {metrics.evidence_validity_rate:.1%}",
        f"- Grounded relation recall: {metrics.grounded_relation_recall:.1%}",
        (
            "- Review summary validity: "
            f"{metrics.review_summary_validity_rate:.1%}"
            if metrics.review_summary_validity_rate is not None
            else "- Review summary validity: not captured"
        ),
        (
            "- Review decision coverage: "
            f"{metrics.review_decision_coverage_rate:.1%}"
            if metrics.review_decision_coverage_rate is not None
            else "- Review decision coverage: not captured"
        ),
        (
            "- Full review completion: "
            f"{metrics.full_review_completion_rate:.1%}"
            if metrics.full_review_completion_rate is not None
            else "- Full review completion: not captured"
        ),
        f"- Controlled capture ready: {report.capture_readiness.controlled_capture_ready}",
        "",
        "## Controlled Capture Evidence",
        "",
    ]
    if report.capture_readiness.failures:
        lines.extend(f"- {failure}" for failure in report.capture_readiness.failures)
    else:
        lines.append("- Complete enough to establish a baseline; this is not a release or materialization decision.")
    lines.append("")
    return "\n".join(lines)


def write_memory_graph_report(report: MemoryGraphEvaluationReport, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "report.json"
    markdown_path = output_dir / "report.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_memory_graph_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def _matches_case_scope(case: MemoryGraphBenchmarkCase, result: MemoryGraphCandidateObservation) -> bool:
    return (
        result.org_id == case.org_id
        and result.project_id == case.project_id
        and result.memory_record_id == case.memory_record_id
    )


def _parse_proposal(result: MemoryGraphCandidateObservation) -> MemoryGraphProposal | None:
    if result.proposal_json is None:
        return None
    try:
        return MemoryGraphProposal.model_validate(result.proposal_json)
    except ValueError:
        return None


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 1.0
    return numerator / denominator


def _evidence_ref_keys(evidence_refs: tuple[MemoryGraphEvidenceRef, ...]) -> set[tuple[str, str]]:
    return {evidence_ref.key for evidence_ref in evidence_refs}


__all__ = [
    "MemoryGraphBenchmarkCase",
    "MemoryGraphBenchmarkDataset",
    "MemoryGraphCandidateObservation",
    "MemoryGraphCaptureReadiness",
    "MemoryGraphEvaluationReport",
    "MemoryGraphEvaluationRun",
    "MemoryGraphMetrics",
    "MemoryGraphReviewSummary",
    "evaluate_memory_graph_capture_readiness",
    "fixture_fingerprint",
    "load_memory_graph_benchmark_dataset",
    "load_memory_graph_evaluation_run",
    "render_memory_graph_markdown",
    "score_memory_graph_run",
    "write_memory_graph_report",
]
