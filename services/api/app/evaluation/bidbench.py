"""BidBench file loading, reporting, and regression thresholds."""

from __future__ import annotations

import json
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


class BidBenchThresholds(BaseModel):
    model_config = ConfigDict(frozen=True)

    min_mandatory_recall: float | None = Field(default=None, ge=0, le=1)
    min_scored_recall: float | None = Field(default=None, ge=0, le=1)
    min_source_association_accuracy: float | None = Field(default=None, ge=0, le=1)
    min_combined_score: float | None = Field(default=None, ge=0, le=1)
    max_unsupported_claim_rate: float | None = Field(default=None, ge=0, le=1)


def evaluate_files(dataset_path: Path, candidate_path: Path) -> BidBenchRunReport:
    dataset_file = _resolve_dataset_file(dataset_path)
    dataset = BidBenchDataset.model_validate_json(dataset_file.read_text(encoding="utf-8"))
    candidate = BidBenchCandidate.model_validate_json(candidate_path.read_text(encoding="utf-8"))
    metrics = score_candidate(dataset, candidate)

    return BidBenchRunReport(
        formula_version=metrics.formula_version,
        generated_at=datetime.now(UTC),
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
    return "\n".join(lines)


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


def _format_percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


__all__ = [
    "BidBenchRunReport",
    "BidBenchThresholds",
    "check_thresholds",
    "evaluate_files",
    "render_markdown",
    "write_report",
]
