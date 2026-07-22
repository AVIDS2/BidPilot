"""Offline quality gates for BidPilot's governed memory context packs.

The evaluator intentionally stores only identifiers, scope metadata, citation
counts, and character counts. It never copies memory bodies into benchmark
artifacts, which keeps evaluation useful without creating a second knowledge
store containing user content.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts import EvaluationEvidenceProvenance, MemoryContextPack, MemoryScope


class _EvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class MemoryBenchmarkCase(_EvaluationModel):
    """One authorized memory-recall scenario with explicit safety boundaries."""

    id: str = Field(min_length=1, max_length=100)
    query: str = Field(min_length=1, max_length=4_000)
    org_id: str = Field(min_length=1, max_length=100)
    user_id: str = Field(min_length=1, max_length=100)
    project_id: str | None = Field(default=None, min_length=1, max_length=100)
    expected_record_ids: tuple[str, ...] = ()
    forbidden_record_ids: tuple[str, ...] = ()
    max_items: int = Field(ge=1, le=24)
    max_characters: int = Field(ge=1, le=48_000)
    required_degraded_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_record_sets(self) -> MemoryBenchmarkCase:
        expected_ids = set(self.expected_record_ids)
        forbidden_ids = set(self.forbidden_record_ids)
        if any(not record_id for record_id in (*self.expected_record_ids, *self.forbidden_record_ids)):
            raise ValueError("memory benchmark record ids must be non-empty")
        if len(expected_ids) != len(self.expected_record_ids):
            raise ValueError("memory benchmark expected_record_ids must be unique")
        if len(forbidden_ids) != len(self.forbidden_record_ids):
            raise ValueError("memory benchmark forbidden_record_ids must be unique")
        if expected_ids & forbidden_ids:
            raise ValueError("memory benchmark expected and forbidden ids must not overlap")
        return self


class MemoryBenchmarkDataset(_EvaluationModel):
    schema_version: str = "1.0"
    dataset_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    dataset_role: str = Field(min_length=1, max_length=30)
    description: str | None = Field(default=None, max_length=4_000)
    cases: tuple[MemoryBenchmarkCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_case_ids(self) -> MemoryBenchmarkDataset:
        case_ids = [case.id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("memory benchmark cases contain duplicate ids")
        return self


class MemoryContextItemObservation(_EvaluationModel):
    """A redacted, scoreable representation of a context item."""

    record_id: str = Field(min_length=1, max_length=100)
    scope: MemoryScope
    owner_user_id: str | None = Field(default=None, min_length=1, max_length=100)
    citation_count: int = Field(ge=0, le=32)
    content_characters: int = Field(ge=0, le=48_000)

    @model_validator(mode="after")
    def validate_private_owner(self) -> MemoryContextItemObservation:
        if self.scope is MemoryScope.USER_PRIVATE and not self.owner_user_id:
            raise ValueError("private memory observation requires owner_user_id")
        return self


class MemoryContextObservation(_EvaluationModel):
    case_id: str = Field(min_length=1, max_length=100)
    org_id: str = Field(min_length=1, max_length=100)
    user_id: str = Field(min_length=1, max_length=100)
    project_id: str | None = Field(default=None, min_length=1, max_length=100)
    memory_version: str = Field(min_length=1, max_length=128)
    items: tuple[MemoryContextItemObservation, ...] = ()
    degraded_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_unique_record_ids(self) -> MemoryContextObservation:
        record_ids = [item.record_id for item in self.items]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("memory context observation contains duplicate record ids")
        return self


class MemoryEvaluationRun(_EvaluationModel):
    schema_version: str = "1.0"
    dataset_id: str = Field(min_length=1, max_length=100)
    fixture_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    policy_version: str = Field(min_length=1, max_length=100)
    retrieval_profile_id: str | None = Field(default=None, min_length=1, max_length=500)
    results: tuple[MemoryContextObservation, ...] = Field(min_length=1)
    git_commit: str | None = Field(default=None, max_length=100)
    provenance: EvaluationEvidenceProvenance | None = None

    @model_validator(mode="after")
    def validate_unique_case_results(self) -> MemoryEvaluationRun:
        case_ids = [result.case_id for result in self.results]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("memory evaluation run contains duplicate case results")
        return self


class MemoryMetricCounts(_EvaluationModel):
    case_count: int = Field(ge=0)
    expected_record_count: int = Field(ge=0)
    expected_record_hit_count: int = Field(ge=0)
    forbidden_record_count: int = Field(ge=0)
    forbidden_record_hit_count: int = Field(ge=0)
    returned_item_count: int = Field(ge=0)
    provenance_valid_item_count: int = Field(ge=0)
    private_item_count: int = Field(ge=0)
    private_owner_match_count: int = Field(ge=0)
    budget_pass_case_count: int = Field(ge=0)
    degraded_mode_case_count: int = Field(ge=0)
    passed_degraded_mode_case_count: int = Field(ge=0)


class MemoryMetrics(_EvaluationModel):
    formula_version: str = "1.0"
    counts: MemoryMetricCounts
    expected_record_recall: float = Field(ge=0, le=1)
    isolation_pass_rate: float = Field(ge=0, le=1)
    provenance_validity_rate: float = Field(ge=0, le=1)
    private_ownership_pass_rate: float = Field(ge=0, le=1)
    context_budget_pass_rate: float = Field(ge=0, le=1)
    degraded_mode_pass_rate: float | None = Field(default=None, ge=0, le=1)


class MemoryEvaluationReport(_EvaluationModel):
    schema_version: str = "1.0"
    generated_at: datetime
    dataset_id: str
    dataset_role: str
    fixture_fingerprint: str
    policy_version: str
    retrieval_profile_id: str | None = None
    git_commit: str | None = None
    provenance: EvaluationEvidenceProvenance | None = None
    metrics: MemoryMetrics


class MemoryComparison(_EvaluationModel):
    valid: bool
    invalid_reasons: tuple[str, ...] = ()
    metric_deltas: dict[str, float] = Field(default_factory=dict)


def fixture_fingerprint(dataset: MemoryBenchmarkDataset) -> str:
    """Fingerprint the complete fixture before any report is compared."""
    payload = json.dumps(
        dataset.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_memory_benchmark_dataset(path: Path) -> MemoryBenchmarkDataset:
    try:
        return MemoryBenchmarkDataset.model_validate_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid memory benchmark dataset: {path}") from exc


def load_memory_evaluation_run(path: Path) -> MemoryEvaluationRun:
    try:
        return MemoryEvaluationRun.model_validate_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid memory evaluation run: {path}") from exc


MemoryContextLoader = Callable[[MemoryBenchmarkCase], MemoryContextPack]


def build_memory_evaluation_run(
    dataset: MemoryBenchmarkDataset,
    *,
    context_loader: MemoryContextLoader,
    policy_version: str,
    retrieval_profile_id: str | None,
    git_commit: str | None = None,
    provenance: EvaluationEvidenceProvenance | None = None,
) -> MemoryEvaluationRun:
    """Adapt context packs into a redacted, deterministic evaluation run."""
    results: list[MemoryContextObservation] = []
    for case in dataset.cases:
        pack = context_loader(case)
        _validate_context_scope(case, pack)
        results.append(
            MemoryContextObservation(
                case_id=case.id,
                org_id=pack.org_id,
                user_id=pack.user_id,
                project_id=pack.project_id,
                memory_version=pack.memory_version,
                items=tuple(
                    MemoryContextItemObservation(
                        record_id=item.record_id,
                        scope=item.scope,
                        owner_user_id=item.owner_user_id,
                        citation_count=len(item.citations),
                        content_characters=len(item.title) + len(item.body_markdown),
                    )
                    for item in pack.items
                ),
                degraded_reasons=pack.degraded_reasons,
            )
        )
    return MemoryEvaluationRun(
        dataset_id=dataset.dataset_id,
        fixture_fingerprint=fixture_fingerprint(dataset),
        policy_version=policy_version,
        retrieval_profile_id=retrieval_profile_id,
        results=tuple(results),
        git_commit=git_commit,
        provenance=provenance,
    )


def score_memory_run(
    dataset: MemoryBenchmarkDataset,
    run: MemoryEvaluationRun,
) -> MemoryEvaluationReport:
    """Score one MemoryBench run without querying a model or memory database."""
    expected_fingerprint = fixture_fingerprint(dataset)
    if run.dataset_id != dataset.dataset_id:
        raise ValueError("memory run dataset_id does not match benchmark dataset")
    if run.fixture_fingerprint != expected_fingerprint:
        raise ValueError("memory run fixture_fingerprint does not match benchmark dataset")

    cases_by_id = {case.id: case for case in dataset.cases}
    results_by_id = {result.case_id: result for result in run.results}
    if set(cases_by_id) != set(results_by_id):
        raise ValueError("memory run must contain exactly one result for each benchmark case")

    expected_record_count = 0
    expected_record_hit_count = 0
    forbidden_record_count = 0
    forbidden_record_hit_count = 0
    returned_item_count = 0
    provenance_valid_item_count = 0
    private_item_count = 0
    private_owner_match_count = 0
    budget_pass_case_count = 0
    isolation_pass_case_count = 0
    degraded_mode_case_count = 0
    passed_degraded_mode_case_count = 0

    for case in dataset.cases:
        result = results_by_id[case.id]
        _validate_observation_scope(case, result)
        returned_ids = {item.record_id for item in result.items}
        expected_ids = set(case.expected_record_ids)
        forbidden_ids = set(case.forbidden_record_ids)

        expected_record_count += len(expected_ids)
        expected_record_hit_count += len(expected_ids & returned_ids)
        forbidden_record_count += len(forbidden_ids)
        forbidden_record_hit_count += len(forbidden_ids & returned_ids)
        returned_item_count += len(result.items)
        provenance_valid_item_count += sum(item.citation_count > 0 for item in result.items)

        private_items = [item for item in result.items if item.scope is MemoryScope.USER_PRIVATE]
        private_item_count += len(private_items)
        private_owner_match_count += sum(item.owner_user_id == case.user_id for item in private_items)

        if not (forbidden_ids & returned_ids):
            isolation_pass_case_count += 1
        if (
            len(result.items) <= case.max_items
            and sum(item.content_characters for item in result.items) <= case.max_characters
        ):
            budget_pass_case_count += 1
        if case.required_degraded_reasons:
            degraded_mode_case_count += 1
            if set(case.required_degraded_reasons).issubset(result.degraded_reasons):
                passed_degraded_mode_case_count += 1

    metrics = MemoryMetrics(
        counts=MemoryMetricCounts(
            case_count=len(dataset.cases),
            expected_record_count=expected_record_count,
            expected_record_hit_count=expected_record_hit_count,
            forbidden_record_count=forbidden_record_count,
            forbidden_record_hit_count=forbidden_record_hit_count,
            returned_item_count=returned_item_count,
            provenance_valid_item_count=provenance_valid_item_count,
            private_item_count=private_item_count,
            private_owner_match_count=private_owner_match_count,
            budget_pass_case_count=budget_pass_case_count,
            degraded_mode_case_count=degraded_mode_case_count,
            passed_degraded_mode_case_count=passed_degraded_mode_case_count,
        ),
        expected_record_recall=_ratio(expected_record_hit_count, expected_record_count, empty=1.0),
        isolation_pass_rate=_ratio(isolation_pass_case_count, len(dataset.cases), empty=1.0),
        provenance_validity_rate=_ratio(provenance_valid_item_count, returned_item_count, empty=1.0),
        private_ownership_pass_rate=_ratio(private_owner_match_count, private_item_count, empty=1.0),
        context_budget_pass_rate=_ratio(budget_pass_case_count, len(dataset.cases), empty=1.0),
        degraded_mode_pass_rate=(
            _ratio(passed_degraded_mode_case_count, degraded_mode_case_count, empty=1.0)
            if degraded_mode_case_count
            else None
        ),
    )
    return MemoryEvaluationReport(
        generated_at=datetime.now(UTC),
        dataset_id=dataset.dataset_id,
        dataset_role=dataset.dataset_role,
        fixture_fingerprint=expected_fingerprint,
        policy_version=run.policy_version,
        retrieval_profile_id=run.retrieval_profile_id,
        git_commit=run.git_commit,
        provenance=run.provenance,
        metrics=metrics,
    )


def compare_memory_reports(
    baseline: MemoryEvaluationReport,
    candidate: MemoryEvaluationReport,
) -> MemoryComparison:
    """Compare reports only when fixture, policy, and retrieval profile match."""
    invalid_reasons = tuple(
        field
        for field in ("dataset_id", "fixture_fingerprint", "policy_version", "retrieval_profile_id")
        if getattr(baseline, field) != getattr(candidate, field)
    )
    if invalid_reasons:
        return MemoryComparison(valid=False, invalid_reasons=invalid_reasons)

    return MemoryComparison(
        valid=True,
        metric_deltas={
            "expected_record_recall": (
                candidate.metrics.expected_record_recall - baseline.metrics.expected_record_recall
            ),
            "isolation_pass_rate": candidate.metrics.isolation_pass_rate - baseline.metrics.isolation_pass_rate,
            "provenance_validity_rate": (
                candidate.metrics.provenance_validity_rate - baseline.metrics.provenance_validity_rate
            ),
            "private_ownership_pass_rate": (
                candidate.metrics.private_ownership_pass_rate - baseline.metrics.private_ownership_pass_rate
            ),
            "context_budget_pass_rate": (
                candidate.metrics.context_budget_pass_rate - baseline.metrics.context_budget_pass_rate
            ),
        },
    )


def render_memory_markdown(report: MemoryEvaluationReport) -> str:
    metrics = report.metrics
    rows: tuple[tuple[str, float | None], ...] = (
        ("Expected record recall", metrics.expected_record_recall),
        ("Isolation pass", metrics.isolation_pass_rate),
        ("Provenance validity", metrics.provenance_validity_rate),
        ("Private ownership pass", metrics.private_ownership_pass_rate),
        ("Context budget pass", metrics.context_budget_pass_rate),
        ("Degraded-mode pass", metrics.degraded_mode_pass_rate),
    )
    lines = [
        "# BidBench Memory Report",
        "",
        f"- Dataset: `{report.dataset_id}` ({report.dataset_role})",
        f"- Policy: `{report.policy_version}`",
        f"- Retrieval profile: `{report.retrieval_profile_id or 'not-configured'}`",
        f"- Fixture fingerprint: `{report.fixture_fingerprint}`",
        "",
        "| Metric | Value |",
        "|---|---:|",
        *(f"| {label} | {_format_ratio(value)} |" for label, value in rows),
        "",
        "## Counts",
        "",
        f"- Cases: {metrics.counts.case_count}",
        f"- Returned items: {metrics.counts.returned_item_count}",
        f"- Forbidden record hits: {metrics.counts.forbidden_record_hit_count}",
        f"- Invalid provenance items: {metrics.counts.returned_item_count - metrics.counts.provenance_valid_item_count}",
    ]
    return "\n".join(lines)


def write_memory_report(report: MemoryEvaluationReport, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "memory-report.json"
    markdown_path = output_dir / "memory-report.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_memory_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def _validate_context_scope(case: MemoryBenchmarkCase, pack: MemoryContextPack) -> None:
    if pack.org_id != case.org_id:
        raise ValueError("memory context pack org_id does not match benchmark case")
    if pack.user_id != case.user_id:
        raise ValueError("memory context pack user_id does not match benchmark case")
    if pack.project_id != case.project_id:
        raise ValueError("memory context pack project_id does not match benchmark case")


def _validate_observation_scope(case: MemoryBenchmarkCase, result: MemoryContextObservation) -> None:
    if result.org_id != case.org_id:
        raise ValueError("memory observation org_id does not match benchmark case")
    if result.user_id != case.user_id:
        raise ValueError("memory observation user_id does not match benchmark case")
    if result.project_id != case.project_id:
        raise ValueError("memory observation project_id does not match benchmark case")


def _ratio(numerator: int, denominator: int, *, empty: float) -> float:
    return numerator / denominator if denominator else empty


def _format_ratio(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


__all__ = [
    "MemoryBenchmarkCase",
    "MemoryBenchmarkDataset",
    "MemoryComparison",
    "MemoryContextItemObservation",
    "MemoryContextObservation",
    "MemoryEvaluationReport",
    "MemoryEvaluationRun",
    "MemoryMetrics",
    "build_memory_evaluation_run",
    "compare_memory_reports",
    "fixture_fingerprint",
    "load_memory_benchmark_dataset",
    "load_memory_evaluation_run",
    "render_memory_markdown",
    "score_memory_run",
    "write_memory_report",
]
