"""Deterministic retrieval-quality metrics for frozen BidBench fixtures."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts import (
    BidBenchLocator,
    BidBenchSource,
    CitationValidationStatus,
    EvaluationEvidenceProvenance,
    RetrievalCandidate,
    RetrievalResult,
)


class _EvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class RetrievalStrategy(StrEnum):
    DENSE = "dense"
    SPARSE = "sparse"
    FUSED = "fused"
    RERANKED = "reranked"


class RetrievalBenchmarkQuery(_EvaluationModel):
    id: str = Field(min_length=1, max_length=100)
    query: str = Field(min_length=1, max_length=4_000)
    authorized_project_id: str = Field(min_length=1, max_length=100)
    relevant_chunk_ids: tuple[str, ...] = Field(min_length=1)
    expected_locators: tuple[BidBenchLocator, ...] = Field(min_length=1)
    mandatory_evidence: bool = False
    required_degraded_reasons: tuple[str, ...] = ()


class RetrievalBenchmarkDataset(_EvaluationModel):
    schema_version: str = "1.0"
    dataset_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    dataset_role: str = Field(min_length=1, max_length=30)
    sources: tuple[BidBenchSource, ...] = Field(min_length=1)
    queries: tuple[RetrievalBenchmarkQuery, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> RetrievalBenchmarkDataset:
        source_ids = [source.id for source in self.sources]
        query_ids = [query.id for query in self.queries]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("retrieval benchmark sources contain duplicate ids")
        if len(query_ids) != len(set(query_ids)):
            raise ValueError("retrieval benchmark queries contain duplicate ids")
        known_sources = set(source_ids)
        for query in self.queries:
            if any(locator.source_id not in known_sources for locator in query.expected_locators):
                raise ValueError(f"query {query.id!r} references an unknown source")
        return self


class RetrievalBenchmarkHit(_EvaluationModel):
    chunk_id: str = Field(min_length=1, max_length=100)
    project_id: str = Field(min_length=1, max_length=100)
    source_id: str = Field(min_length=1, max_length=100)
    locator: BidBenchLocator | None = None
    locator_validation_status: CitationValidationStatus = CitationValidationStatus.PARTIAL


class RetrievalQueryResult(_EvaluationModel):
    query_id: str = Field(min_length=1, max_length=100)
    hits: tuple[RetrievalBenchmarkHit, ...] = ()
    profile_id: str | None = Field(default=None, min_length=1, max_length=500)
    degraded_reasons: tuple[str, ...] = ()


class RetrievalEvaluationRun(_EvaluationModel):
    schema_version: str = "1.0"
    dataset_id: str = Field(min_length=1, max_length=100)
    fixture_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    retrieval_profile_id: str = Field(min_length=1, max_length=500)
    strategy: RetrievalStrategy
    candidate_limit: int = Field(ge=1, le=100)
    results: tuple[RetrievalQueryResult, ...] = Field(min_length=1)
    git_commit: str | None = Field(default=None, max_length=100)
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=255)
    latency_ms: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    provenance: EvaluationEvidenceProvenance | None = None

    @model_validator(mode="after")
    def validate_unique_results(self) -> RetrievalEvaluationRun:
        query_ids = [result.query_id for result in self.results]
        if len(query_ids) != len(set(query_ids)):
            raise ValueError("retrieval run contains duplicate query results")
        return self


class RetrievalMetricCounts(_EvaluationModel):
    query_count: int
    returned_hit_count: int
    relevant_hit_count: int
    verified_locator_hit_count: int
    mandatory_query_count: int
    mandatory_queries_with_evidence: int
    cross_project_hit_count: int
    degraded_mode_case_count: int
    passed_degraded_mode_case_count: int


class RetrievalMetrics(_EvaluationModel):
    formula_version: str = "1.0"
    counts: RetrievalMetricCounts
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float
    mean_reciprocal_rank: float
    locator_validity_rate: float
    mandatory_evidence_recall: float
    cross_project_denial_rate: float
    degraded_mode_pass_rate: float | None


class RetrievalEvaluationReport(_EvaluationModel):
    schema_version: str = "1.0"
    generated_at: datetime
    dataset_id: str
    dataset_role: str
    fixture_fingerprint: str
    retrieval_profile_id: str
    strategy: RetrievalStrategy
    candidate_limit: int
    git_commit: str | None = None
    provider: str | None = None
    model: str | None = None
    latency_ms: int | None = None
    estimated_cost_usd: float | None = None
    provenance: EvaluationEvidenceProvenance | None = None
    metrics: RetrievalMetrics


class RetrievalComparison(_EvaluationModel):
    valid: bool
    invalid_reasons: tuple[str, ...] = ()
    metric_deltas: dict[str, float] = Field(default_factory=dict)


def fixture_fingerprint(dataset: RetrievalBenchmarkDataset) -> str:
    """Fingerprint every label and source hash before comparing retrieval methods."""
    payload = json.dumps(
        dataset.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_retrieval_benchmark_dataset(path: Path) -> RetrievalBenchmarkDataset:
    """Load a benchmark and verify that its frozen source files did not change."""
    try:
        dataset = RetrievalBenchmarkDataset.model_validate_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid retrieval benchmark dataset: {path}") from exc

    root = path.parent.resolve()
    for source in dataset.sources:
        source_path = (root / source.path).resolve()
        if not source_path.is_relative_to(root):
            raise ValueError(f"retrieval source path escapes dataset directory: {source.path}")
        if not source_path.is_file():
            raise ValueError(f"retrieval source file not found: {source.path}")
        canonical = source_path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
        actual_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if actual_hash.casefold() != source.sha256.casefold():
            raise ValueError(f"retrieval source sha256 mismatch for {source.id}")
    return dataset


def load_retrieval_evaluation_run(path: Path) -> RetrievalEvaluationRun:
    try:
        return RetrievalEvaluationRun.model_validate_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid retrieval evaluation run: {path}") from exc


RetrievalRunner = Callable[[RetrievalBenchmarkQuery], RetrievalResult]


def build_retrieval_evaluation_run(
    dataset: RetrievalBenchmarkDataset,
    *,
    retriever: RetrievalRunner,
    source_id_by_document_id: Mapping[str, str],
    retrieval_profile_id: str,
    strategy: RetrievalStrategy,
    candidate_limit: int,
    git_commit: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    latency_ms: int | None = None,
    estimated_cost_usd: float | None = None,
    provenance: EvaluationEvidenceProvenance | None = None,
) -> RetrievalEvaluationRun:
    """Adapt the shared runtime contract into a deterministic benchmark run.

    The explicit source-id map is deliberate: benchmark provenance is never
    inferred from a filename or document similarity. An unmapped source can be
    measured as a retrieval hit but cannot receive locator credit.
    """
    results: list[RetrievalQueryResult] = []
    for query in dataset.queries:
        retrieval_result = retriever(query)
        if retrieval_result.project_id != query.authorized_project_id:
            raise ValueError("retriever returned a result for the wrong authorized project")
        if (
            retrieval_result.profile_id is not None
            and retrieval_result.profile_id != retrieval_profile_id
        ):
            raise ValueError("retriever result profile does not match evaluation run profile")
        hits = tuple(
            _to_benchmark_hit(candidate, source_id_by_document_id)
            for candidate in retrieval_result.candidates
        )
        results.append(
            RetrievalQueryResult(
                query_id=query.id,
                hits=hits,
                profile_id=retrieval_result.profile_id,
                degraded_reasons=retrieval_result.degraded_reasons,
            )
        )
    return RetrievalEvaluationRun(
        dataset_id=dataset.dataset_id,
        fixture_fingerprint=fixture_fingerprint(dataset),
        retrieval_profile_id=retrieval_profile_id,
        strategy=strategy,
        candidate_limit=candidate_limit,
        results=tuple(results),
        git_commit=git_commit,
        provider=provider,
        model=model,
        latency_ms=latency_ms,
        estimated_cost_usd=estimated_cost_usd,
        provenance=provenance,
    )


def score_retrieval_run(
    dataset: RetrievalBenchmarkDataset,
    run: RetrievalEvaluationRun,
) -> RetrievalEvaluationReport:
    """Score one run without any provider call or fuzzy post-hoc matching."""
    expected_fingerprint = fixture_fingerprint(dataset)
    if run.dataset_id != dataset.dataset_id:
        raise ValueError("retrieval run dataset_id does not match benchmark dataset")
    if run.fixture_fingerprint != expected_fingerprint:
        raise ValueError("retrieval run fixture_fingerprint does not match benchmark dataset")

    queries_by_id = {query.id: query for query in dataset.queries}
    results_by_id = {result.query_id: result for result in run.results}
    if set(results_by_id) != set(queries_by_id):
        raise ValueError("retrieval run must contain exactly one result for each benchmark query")

    recalls: dict[int, list[float]] = {1: [], 3: [], 5: [], 10: []}
    reciprocal_ranks: list[float] = []
    returned_hit_count = 0
    relevant_hit_count = 0
    verified_locator_hit_count = 0
    mandatory_query_count = 0
    mandatory_queries_with_evidence = 0
    cross_project_hit_count = 0
    degraded_mode_case_count = 0
    passed_degraded_mode_case_count = 0

    for query in dataset.queries:
        result = results_by_id[query.id]
        if result.profile_id is not None and result.profile_id != run.retrieval_profile_id:
            raise ValueError("retrieval query result profile_id does not match evaluation run profile")
        hits = result.hits
        returned_hit_count += len(hits)
        cross_project_hit_count += sum(hit.project_id != query.authorized_project_id for hit in hits)

        first_relevant_rank: int | None = None
        query_has_relevant_evidence = False
        for rank, hit in enumerate(hits, start=1):
            if hit.project_id != query.authorized_project_id or hit.chunk_id not in query.relevant_chunk_ids:
                continue
            query_has_relevant_evidence = True
            relevant_hit_count += 1
            if first_relevant_rank is None:
                first_relevant_rank = rank
            if _is_verified_expected_locator(hit, query.expected_locators):
                verified_locator_hit_count += 1

        for cutoff, values in recalls.items():
            values.append(1.0 if first_relevant_rank is not None and first_relevant_rank <= cutoff else 0.0)
        reciprocal_ranks.append(1.0 / first_relevant_rank if first_relevant_rank is not None else 0.0)

        if query.mandatory_evidence:
            mandatory_query_count += 1
            if query_has_relevant_evidence:
                mandatory_queries_with_evidence += 1

        if query.required_degraded_reasons:
            degraded_mode_case_count += 1
            if set(query.required_degraded_reasons).issubset(result.degraded_reasons):
                passed_degraded_mode_case_count += 1

    metrics = RetrievalMetrics(
        counts=RetrievalMetricCounts(
            query_count=len(dataset.queries),
            returned_hit_count=returned_hit_count,
            relevant_hit_count=relevant_hit_count,
            verified_locator_hit_count=verified_locator_hit_count,
            mandatory_query_count=mandatory_query_count,
            mandatory_queries_with_evidence=mandatory_queries_with_evidence,
            cross_project_hit_count=cross_project_hit_count,
            degraded_mode_case_count=degraded_mode_case_count,
            passed_degraded_mode_case_count=passed_degraded_mode_case_count,
        ),
        recall_at_1=_average(recalls[1]),
        recall_at_3=_average(recalls[3]),
        recall_at_5=_average(recalls[5]),
        recall_at_10=_average(recalls[10]),
        mean_reciprocal_rank=_average(reciprocal_ranks),
        locator_validity_rate=_ratio(verified_locator_hit_count, relevant_hit_count, empty=1.0),
        mandatory_evidence_recall=_ratio(
            mandatory_queries_with_evidence,
            mandatory_query_count,
            empty=1.0,
        ),
        cross_project_denial_rate=_ratio(
            returned_hit_count - cross_project_hit_count,
            returned_hit_count,
            empty=1.0,
        ),
        degraded_mode_pass_rate=(
            _ratio(passed_degraded_mode_case_count, degraded_mode_case_count)
            if degraded_mode_case_count
            else None
        ),
    )
    return RetrievalEvaluationReport(
        generated_at=datetime.now(UTC),
        dataset_id=dataset.dataset_id,
        dataset_role=dataset.dataset_role,
        fixture_fingerprint=expected_fingerprint,
        retrieval_profile_id=run.retrieval_profile_id,
        strategy=run.strategy,
        candidate_limit=run.candidate_limit,
        git_commit=run.git_commit,
        provider=run.provider,
        model=run.model,
        latency_ms=run.latency_ms,
        estimated_cost_usd=run.estimated_cost_usd,
        provenance=run.provenance,
        metrics=metrics,
    )


def compare_retrieval_reports(
    baseline: RetrievalEvaluationReport,
    candidate: RetrievalEvaluationReport,
) -> RetrievalComparison:
    """Compare runs only when their source fixture and vector profile match."""
    invalid_reasons: list[str] = []
    for field in ("dataset_id", "fixture_fingerprint", "retrieval_profile_id"):
        if getattr(baseline, field) != getattr(candidate, field):
            invalid_reasons.append(field)
    if invalid_reasons:
        return RetrievalComparison(valid=False, invalid_reasons=tuple(invalid_reasons))

    metric_deltas = {
        "recall_at_1": candidate.metrics.recall_at_1 - baseline.metrics.recall_at_1,
        "recall_at_3": candidate.metrics.recall_at_3 - baseline.metrics.recall_at_3,
        "recall_at_5": candidate.metrics.recall_at_5 - baseline.metrics.recall_at_5,
        "recall_at_10": candidate.metrics.recall_at_10 - baseline.metrics.recall_at_10,
        "mean_reciprocal_rank": (
            candidate.metrics.mean_reciprocal_rank - baseline.metrics.mean_reciprocal_rank
        ),
        "locator_validity_rate": (
            candidate.metrics.locator_validity_rate - baseline.metrics.locator_validity_rate
        ),
        "mandatory_evidence_recall": (
            candidate.metrics.mandatory_evidence_recall - baseline.metrics.mandatory_evidence_recall
        ),
        "cross_project_denial_rate": (
            candidate.metrics.cross_project_denial_rate - baseline.metrics.cross_project_denial_rate
        ),
    }
    return RetrievalComparison(valid=True, metric_deltas=metric_deltas)


def render_retrieval_markdown(report: RetrievalEvaluationReport) -> str:
    metrics = report.metrics
    lines = [
        "# BidBench Retrieval Report",
        "",
        f"- Dataset: `{report.dataset_id}` ({report.dataset_role})",
        f"- Strategy: `{report.strategy.value}`",
        f"- Profile: `{report.retrieval_profile_id}`",
        f"- Fixture fingerprint: `{report.fixture_fingerprint}`",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    rows: tuple[tuple[str, float | None], ...] = (
        ("Recall@1", metrics.recall_at_1),
        ("Recall@3", metrics.recall_at_3),
        ("Recall@5", metrics.recall_at_5),
        ("Recall@10", metrics.recall_at_10),
        ("MRR", metrics.mean_reciprocal_rank),
        ("Locator validity", metrics.locator_validity_rate),
        ("Mandatory evidence recall", metrics.mandatory_evidence_recall),
        ("Cross-project denial", metrics.cross_project_denial_rate),
        ("Degraded-mode pass", metrics.degraded_mode_pass_rate),
    )
    lines.extend(f"| {label} | {_format_ratio(value)} |" for label, value in rows)
    lines.extend(
        (
            "",
            "## Counts",
            "",
            f"- Queries: {metrics.counts.query_count}",
            f"- Returned hits: {metrics.counts.returned_hit_count}",
            f"- Relevant hits: {metrics.counts.relevant_hit_count}",
            f"- Cross-project hits: {metrics.counts.cross_project_hit_count}",
        )
    )
    return "\n".join(lines)


def write_retrieval_report(report: RetrievalEvaluationReport, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "retrieval-report.json"
    markdown_path = output_dir / "retrieval-report.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_retrieval_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def _is_verified_expected_locator(
    hit: RetrievalBenchmarkHit,
    expected_locators: tuple[BidBenchLocator, ...],
) -> bool:
    return (
        hit.locator_validation_status is CitationValidationStatus.VERIFIED
        and hit.locator is not None
        and any(_locator_matches(hit.locator, expected) for expected in expected_locators)
    )


def _to_benchmark_hit(
    candidate: RetrievalCandidate,
    source_id_by_document_id: Mapping[str, str],
) -> RetrievalBenchmarkHit:
    source_id = source_id_by_document_id.get(candidate.source_document_id, "unmapped-source")
    locator = None
    if any(
        (
            candidate.locator.page,
            candidate.locator.heading,
            candidate.locator.table,
            candidate.locator.text_anchor,
        )
    ):
        locator = BidBenchLocator(
            source_id=source_id,
            page=candidate.locator.page,
            section=candidate.locator.heading,
            table=candidate.locator.table,
            text_anchor=candidate.locator.text_anchor,
        )
    return RetrievalBenchmarkHit(
        chunk_id=candidate.chunk_id,
        project_id=candidate.project_id,
        source_id=source_id,
        locator=locator,
        locator_validation_status=candidate.locator.validation_status,
    )


def _locator_matches(candidate: BidBenchLocator, expected: BidBenchLocator) -> bool:
    if candidate.source_id != expected.source_id:
        return False
    checks: list[bool] = []
    if candidate.page is not None and expected.page is not None:
        checks.append(candidate.page == expected.page)
    if candidate.section and expected.section:
        checks.append(_normalize_text(candidate.section) == _normalize_text(expected.section))
    if candidate.table and expected.table:
        checks.append(_normalize_text(candidate.table) == _normalize_text(expected.table))
    if candidate.text_anchor and expected.text_anchor:
        candidate_anchor = _normalize_text(candidate.text_anchor)
        expected_anchor = _normalize_text(expected.text_anchor)
        checks.append(
            candidate_anchor == expected_anchor
            or (len(expected_anchor) >= 8 and expected_anchor in candidate_anchor)
            or (len(candidate_anchor) >= 8 and candidate_anchor in expected_anchor)
        )
    return any(checks)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(
        character
        for character in normalized
        if not character.isspace() and not unicodedata.category(character).startswith("P")
    )


def _ratio(numerator: int, denominator: int, *, empty: float = 0.0) -> float:
    return numerator / denominator if denominator else empty


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _format_ratio(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


__all__ = [
    "RetrievalBenchmarkDataset",
    "RetrievalBenchmarkHit",
    "RetrievalBenchmarkQuery",
    "RetrievalComparison",
    "RetrievalEvaluationReport",
    "RetrievalEvaluationRun",
    "RetrievalMetricCounts",
    "RetrievalMetrics",
    "RetrievalQueryResult",
    "RetrievalStrategy",
    "build_retrieval_evaluation_run",
    "compare_retrieval_reports",
    "fixture_fingerprint",
    "load_retrieval_benchmark_dataset",
    "load_retrieval_evaluation_run",
    "render_retrieval_markdown",
    "score_retrieval_run",
    "write_retrieval_report",
]
