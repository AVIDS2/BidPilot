"""Offline, deterministic evaluation primitives for the Pi-style harness.

The design follows the useful part of public agent-evaluation tooling: compare
observable tool trajectories instead of guessing quality from prose.  It does
not send traces, project data, or provider output to a hosted evaluator.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field


class _HarnessEvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class TrajectoryMatchMode(StrEnum):
    """Explicit matching modes inspired by public agent trajectory evaluators.

    ``subset`` means every expected item must occur in the observed trace;
    ``superset`` means the observed trace may not contain an unexpected item.
    Keeping this direction in the type documentation prevents a misleading
    green result when a safety-critical extra tool call occurred.
    """

    STRICT = "strict"
    UNORDERED = "unordered"
    SUBSET = "subset"
    SUPERSET = "superset"


class TrajectoryMatch(_HarnessEvaluationModel):
    mode: TrajectoryMatchMode
    expected: tuple[str, ...]
    actual: tuple[str, ...]
    passed: bool
    missing: tuple[str, ...] = ()
    unexpected: tuple[str, ...] = ()


class GraphTrajectory(_HarnessEvaluationModel):
    """A graph run reduced to public node and directed-edge labels."""

    nodes: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]


class GraphTrajectoryMatch(_HarnessEvaluationModel):
    node_match: TrajectoryMatch
    edge_match: TrajectoryMatch
    passed: bool


HarnessDimension = Literal[
    "contracts",
    "loop_recovery",
    "cross_domain",
    "bidpilot",
    "langgraph",
]

_DIMENSION_WEIGHTS: dict[HarnessDimension, int] = {
    "contracts": 35,
    "loop_recovery": 30,
    "cross_domain": 15,
    "bidpilot": 15,
    "langgraph": 5,
}


class HarnessEvaluationCase(_HarnessEvaluationModel):
    id: str = Field(min_length=1, max_length=120)
    dimension: HarnessDimension
    passed: bool
    p0: bool = False
    detail: str = Field(min_length=1, max_length=500)


class HarnessDimensionScore(_HarnessEvaluationModel):
    dimension: HarnessDimension
    case_count: int = Field(ge=1)
    passed_case_count: int = Field(ge=0)
    weight: int = Field(ge=1, le=100)
    score: float = Field(ge=0, le=100)


class HarnessEvaluationReport(_HarnessEvaluationModel):
    schema_version: Literal["1.0"] = "1.0"
    generated_at: datetime
    suite_id: str = Field(min_length=1, max_length=120)
    dimensions: tuple[HarnessDimensionScore, ...]
    total_case_count: int = Field(ge=1)
    passed_case_count: int = Field(ge=0)
    p0_failures: tuple[str, ...] = ()
    raw_score: float = Field(ge=0, le=100)
    engineering_score: float = Field(ge=0, le=100)
    passed: bool
    caveats: tuple[str, ...] = ()


def match_trajectory(
    actual: Sequence[str],
    expected: Sequence[str],
    *,
    mode: TrajectoryMatchMode = TrajectoryMatchMode.STRICT,
) -> TrajectoryMatch:
    """Compare a redacted trace without any LLM judge.

    A trace item normally takes the compact form ``tool.succeeded:open_page``
    or ``run.paused:needs_approval``.  The evaluator deliberately does not
    receive model prompts, tool arguments, customer content, or raw errors.
    """
    actual_items = tuple(actual)
    expected_items = tuple(expected)
    if mode is TrajectoryMatchMode.STRICT:
        passed = actual_items == expected_items
        return TrajectoryMatch(
            mode=mode,
            expected=expected_items,
            actual=actual_items,
            passed=passed,
            missing=_counter_delta(expected_items, actual_items),
            unexpected=_counter_delta(actual_items, expected_items),
        )
    if mode is TrajectoryMatchMode.UNORDERED:
        passed = Counter(actual_items) == Counter(expected_items)
        return TrajectoryMatch(
            mode=mode,
            expected=expected_items,
            actual=actual_items,
            passed=passed,
            missing=_counter_delta(expected_items, actual_items),
            unexpected=_counter_delta(actual_items, expected_items),
        )
    if mode is TrajectoryMatchMode.SUBSET:
        missing = _counter_delta(expected_items, actual_items)
        return TrajectoryMatch(
            mode=mode,
            expected=expected_items,
            actual=actual_items,
            passed=not missing,
            missing=missing,
            unexpected=_counter_delta(actual_items, expected_items),
        )
    unexpected = _counter_delta(actual_items, expected_items)
    return TrajectoryMatch(
        mode=mode,
        expected=expected_items,
        actual=actual_items,
        passed=not unexpected,
        missing=_counter_delta(expected_items, actual_items),
        unexpected=unexpected,
    )


def match_graph_trajectory(
    actual: GraphTrajectory,
    expected: GraphTrajectory,
    *,
    mode: TrajectoryMatchMode = TrajectoryMatchMode.STRICT,
) -> GraphTrajectoryMatch:
    """Compare both the visited nodes and actual state transitions of a graph."""
    node_match = match_trajectory(actual.nodes, expected.nodes, mode=mode)
    edge_match = match_trajectory(
        tuple(f"{source}->{target}" for source, target in actual.edges),
        tuple(f"{source}->{target}" for source, target in expected.edges),
        mode=mode,
    )
    return GraphTrajectoryMatch(
        node_match=node_match,
        edge_match=edge_match,
        passed=node_match.passed and edge_match.passed,
    )


def score_harness_cases(
    cases: Sequence[HarnessEvaluationCase],
    *,
    suite_id: str = "pi-harness-v1",
    caveats: Sequence[str] = (),
) -> HarnessEvaluationReport:
    """Calculate the reviewed score from deterministic case outcomes.

    A failed P0 contract caps the score at 59.  This makes a collection of
    pleasant-but-noncritical cases unable to hide a permission, duplicate-side
    effect, cancellation, or remote-download-safety regression.
    """
    if not cases:
        raise ValueError("harness evaluation requires at least one case")
    duplicate_ids = [case.id for case in cases]
    if len(duplicate_ids) != len(set(duplicate_ids)):
        raise ValueError("harness evaluation case ids must be unique")

    dimensions: list[HarnessDimensionScore] = []
    weighted_score = 0.0
    for dimension, weight in _DIMENSION_WEIGHTS.items():
        grouped = [case for case in cases if case.dimension == dimension]
        if not grouped:
            continue
        passed_count = sum(case.passed for case in grouped)
        ratio = passed_count / len(grouped)
        weighted_score += ratio * weight
        dimensions.append(
            HarnessDimensionScore(
                dimension=dimension,
                case_count=len(grouped),
                passed_case_count=passed_count,
                weight=weight,
                score=ratio * 100,
            )
        )
    observed_weight = sum(item.weight for item in dimensions)
    if observed_weight != 100:
        raise ValueError("harness evaluation must cover every weighted dimension")

    p0_failures = tuple(case.id for case in cases if case.p0 and not case.passed)
    engineering_score = min(weighted_score, 59.0) if p0_failures else weighted_score
    return HarnessEvaluationReport(
        generated_at=datetime.now(UTC),
        suite_id=suite_id,
        dimensions=tuple(dimensions),
        total_case_count=len(cases),
        passed_case_count=sum(case.passed for case in cases),
        p0_failures=p0_failures,
        raw_score=weighted_score,
        engineering_score=engineering_score,
        passed=not p0_failures and all(case.passed for case in cases),
        caveats=tuple(caveats),
    )


def render_harness_markdown(report: HarnessEvaluationReport) -> str:
    lines = [
        "# Pi-style Harness Evaluation",
        "",
        f"- Suite: `{report.suite_id}`",
        f"- Cases: {report.passed_case_count}/{report.total_case_count}",
        f"- Raw score: {report.raw_score:.1f}/100",
        f"- Engineering score: {report.engineering_score:.1f}/100",
        f"- P0 failures: {', '.join(report.p0_failures) if report.p0_failures else 'none'}",
        f"- Passed: {report.passed}",
        "",
        "## Dimensions",
        "",
        "| Dimension | Passed | Weight | Score |",
        "|---|---:|---:|---:|",
    ]
    lines.extend(
        f"| {item.dimension} | {item.passed_case_count}/{item.case_count} | {item.weight}% | {item.score:.1f}% |"
        for item in report.dimensions
    )
    lines.extend(("", "## Caveats", ""))
    lines.extend(f"- {item}" for item in report.caveats) if report.caveats else lines.append("- None")
    return "\n".join(lines)


def write_harness_report(report: HarnessEvaluationReport, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "report.json"
    markdown_path = output_dir / "report.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_harness_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def _counter_delta(left: Sequence[str], right: Sequence[str]) -> tuple[str, ...]:
    remaining = Counter(left)
    remaining.subtract(Counter(right))
    return tuple(item for item, count in remaining.items() for _ in range(max(0, count)))


__all__ = [
    "GraphTrajectory",
    "GraphTrajectoryMatch",
    "HarnessDimensionScore",
    "HarnessEvaluationCase",
    "HarnessEvaluationReport",
    "TrajectoryMatch",
    "TrajectoryMatchMode",
    "match_graph_trajectory",
    "match_trajectory",
    "render_harness_markdown",
    "score_harness_cases",
    "write_harness_report",
]
