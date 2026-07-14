"""BidBench file loading, reporting, and regression thresholds."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from contracts import BidBenchCandidate, BidBenchDataset

from .metrics import BidBenchMetrics, score_candidate


class BidBenchRunReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    formula_version: str
    generated_at: datetime
    input_fingerprint: str
    dataset_sha256: str
    candidate_sha256: str
    source_hashes: dict[str, str]
    dataset_id: str
    dataset_title: str
    dataset_role: str
    candidate_id: str
    system_name: str
    git_commit: str | None = None
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    run_number: int
    latency_ms: int | None = None
    estimated_cost_usd: float | None = None
    metrics: BidBenchMetrics
    gate: "BidBenchGateResult | None" = None


class BidBenchThresholds(BaseModel):
    model_config = ConfigDict(frozen=True)

    min_mandatory_recall: float | None = Field(default=None, ge=0, le=1)
    min_scored_recall: float | None = Field(default=None, ge=0, le=1)
    min_source_association_accuracy: float | None = Field(default=None, ge=0, le=1)
    min_combined_score: float | None = Field(default=None, ge=0, le=1)
    max_unsupported_claim_rate: float | None = Field(default=None, ge=0, le=1)


class BidBenchGateResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: str
    passed: bool | None
    thresholds: BidBenchThresholds
    failures: list[str] = Field(default_factory=list)


BidBenchRunReport.model_rebuild()


def evaluate_files(dataset_path: Path, candidate_path: Path) -> BidBenchRunReport:
    dataset_file = _resolve_dataset_file(dataset_path)
    dataset_bytes = dataset_file.read_bytes()
    candidate_bytes = candidate_path.read_bytes()
    dataset = BidBenchDataset.model_validate_json(dataset_bytes)
    candidate = BidBenchCandidate.model_validate_json(candidate_bytes)
    source_hashes = _verify_source_hashes(dataset_file.parent, dataset)
    dataset_sha256 = hashlib.sha256(dataset_bytes).hexdigest()
    candidate_sha256 = hashlib.sha256(candidate_bytes).hexdigest()
    fingerprint_payload = "|".join(
        [dataset_sha256, candidate_sha256, *[source_hashes[key] for key in sorted(source_hashes)]]
    ).encode("utf-8")
    input_fingerprint = hashlib.sha256(fingerprint_payload).hexdigest()
    metrics = score_candidate(dataset, candidate)

    return BidBenchRunReport(
        formula_version=metrics.formula_version,
        generated_at=datetime.now(UTC),
        input_fingerprint=input_fingerprint,
        dataset_sha256=dataset_sha256,
        candidate_sha256=candidate_sha256,
        source_hashes=source_hashes,
        dataset_id=dataset.dataset_id,
        dataset_title=dataset.title,
        dataset_role=dataset.dataset_role.value,
        candidate_id=candidate.candidate_id,
        system_name=candidate.system_name,
        git_commit=candidate.git_commit,
        provider=candidate.provider,
        model=candidate.model,
        prompt_version=candidate.prompt_version,
        run_number=candidate.run_number,
        latency_ms=candidate.latency_ms,
        estimated_cost_usd=candidate.estimated_cost_usd,
        metrics=metrics,
    )


def render_markdown(report: BidBenchRunReport) -> str:
    metrics = report.metrics
    rows = [
        ("Requirement recall", metrics.requirement_recall),
        ("Requirement precision", metrics.requirement_precision),
        ("Requirement F1", metrics.requirement_f1),
        ("Mandatory recall", metrics.mandatory_recall),
        ("Scored recall", metrics.scored_recall),
        ("Scored weight recall", metrics.scored_weight_recall),
        ("Classification accuracy", metrics.classification_accuracy),
        ("Coverage accuracy", metrics.coverage_accuracy),
        ("Source association accuracy", metrics.source_association_accuracy),
        ("Evidence precision", metrics.evidence_precision),
        ("Evidence recall", metrics.evidence_recall),
        ("Evidence F1", metrics.evidence_f1),
        ("Unsupported claim rate", metrics.unsupported_claim_rate),
        ("Completeness score", metrics.completeness_score),
        ("Traceability score", metrics.traceability_score),
        ("Combined score", metrics.combined_score),
    ]

    lines = [
        "# BidBench Report",
        "",
        f"- Dataset: `{report.dataset_id}` ({report.dataset_role})",
        f"- Candidate: `{report.candidate_id}`",
        f"- System: `{report.system_name}`",
        f"- Formula: `{report.formula_version}`",
        f"- Matching: `{metrics.matching_policy}`",
        f"- Input fingerprint: `{report.input_fingerprint}`",
        f"- Generated: `{report.generated_at.isoformat()}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    lines.extend(f"| {label} | {_format_percent(value)} |" for label, value in rows)
    lines.extend(
        [
            "",
            "## Counts",
            "",
            f"- Ground-truth requirements: {metrics.counts.ground_truth_requirements}",
            f"- Candidate requirements: {metrics.counts.candidate_requirements}",
            f"- Matched requirements: {metrics.counts.matched_requirements}",
            f"- Expected evidence links: {metrics.counts.expected_evidence_links}",
            f"- Candidate evidence links: {metrics.counts.candidate_evidence_links}",
            f"- Accepted claims: {metrics.counts.accepted_claims}",
            f"- Unsupported claims: {metrics.counts.unsupported_claims}",
            "",
        ]
    )
    if report.gate is not None:
        lines.extend(
            [
                "## Gate",
                "",
                f"- Mode: `{report.gate.mode}`",
                f"- Passed: `{report.gate.passed}`",
                f"- Failures: {len(report.gate.failures)}",
                "",
            ]
        )
    return "\n".join(lines)


def apply_thresholds(
    report: BidBenchRunReport,
    thresholds: BidBenchThresholds,
    *,
    informational: bool = False,
) -> BidBenchRunReport:
    failures = [] if informational else check_thresholds(report, thresholds)
    gate = BidBenchGateResult(
        mode="informational" if informational else "threshold",
        passed=None if informational else not failures,
        thresholds=thresholds,
        failures=failures,
    )
    return report.model_copy(update={"gate": gate})


def write_report(report: BidBenchRunReport, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "report.json"
    markdown_path = output_dir / "report.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def check_thresholds(
    report: BidBenchRunReport,
    thresholds: BidBenchThresholds,
) -> list[str]:
    metrics = report.metrics
    failures: list[str] = []
    minimums = {
        "mandatory_recall": (metrics.mandatory_recall, thresholds.min_mandatory_recall),
        "scored_recall": (metrics.scored_recall, thresholds.min_scored_recall),
        "source_association_accuracy": (
            metrics.source_association_accuracy,
            thresholds.min_source_association_accuracy,
        ),
        "combined_score": (metrics.combined_score, thresholds.min_combined_score),
    }
    for name, (actual, minimum) in minimums.items():
        if minimum is not None and actual < minimum:
            failures.append(f"{name}={actual:.4f} is below minimum {minimum:.4f}")

    maximum = thresholds.max_unsupported_claim_rate
    if maximum is not None:
        actual = metrics.unsupported_claim_rate
        if actual is None:
            failures.append("unsupported_claim_rate is unavailable because the candidate has no accepted claims")
        elif actual > maximum:
            failures.append(
                f"unsupported_claim_rate={actual:.4f} exceeds maximum {maximum:.4f}"
            )
    return failures


def _resolve_dataset_file(path: Path) -> Path:
    return path / "dataset.json" if path.is_dir() else path


def _verify_source_hashes(
    dataset_dir: Path,
    dataset: BidBenchDataset,
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    resolved_dataset_dir = dataset_dir.resolve()
    for source in dataset.sources:
        source_path = (dataset_dir / source.path).resolve()
        if not source_path.is_relative_to(resolved_dataset_dir):
            raise ValueError(f"source path escapes dataset directory: {source.path}")
        if not source_path.is_file():
            raise ValueError(f"source file not found: {source.path}")
        actual = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if actual.casefold() != source.sha256.casefold():
            raise ValueError(
                f"source sha256 mismatch for {source.id}: expected {source.sha256}, got {actual}"
            )
        hashes[source.id] = actual
    return hashes


def _format_percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


__all__ = [
    "BidBenchGateResult",
    "BidBenchRunReport",
    "BidBenchThresholds",
    "apply_thresholds",
    "check_thresholds",
    "evaluate_files",
    "render_markdown",
    "write_report",
]
