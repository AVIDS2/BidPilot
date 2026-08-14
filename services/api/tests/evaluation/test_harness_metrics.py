from __future__ import annotations

import pytest

from app.evaluation.harness_metrics import (
    GraphTrajectory,
    HarnessEvaluationCase,
    TrajectoryMatchMode,
    match_graph_trajectory,
    match_trajectory,
    score_harness_cases,
)


@pytest.mark.parametrize(
    ("mode", "actual", "expected", "passed"),
    [
        (TrajectoryMatchMode.STRICT, ("a", "b"), ("a", "b"), True),
        (TrajectoryMatchMode.STRICT, ("b", "a"), ("a", "b"), False),
        (TrajectoryMatchMode.UNORDERED, ("b", "a"), ("a", "b"), True),
        (TrajectoryMatchMode.SUBSET, ("a", "b", "c"), ("a", "b"), True),
        (TrajectoryMatchMode.SUPERSET, ("a", "b"), ("a", "b", "c"), True),
        (TrajectoryMatchMode.SUPERSET, ("a", "x"), ("a", "b"), False),
    ],
)
def test_trajectory_modes_make_extra_tool_calls_visible(mode, actual, expected, passed) -> None:
    match = match_trajectory(actual, expected, mode=mode)

    assert match.passed is passed


def test_graph_trajectory_checks_nodes_and_transitions() -> None:
    expected = GraphTrajectory(
        nodes=("plan", "prepare", "execute", "complete"),
        edges=(("plan", "prepare"), ("prepare", "execute"), ("execute", "complete")),
    )
    actual = GraphTrajectory(
        nodes=("plan", "prepare", "execute", "complete"),
        edges=(("plan", "prepare"), ("prepare", "execute"), ("execute", "complete")),
    )

    assert match_graph_trajectory(actual, expected).passed is True
    bad = GraphTrajectory(
        nodes=actual.nodes,
        edges=(("plan", "execute"), ("execute", "complete")),
    )
    assert match_graph_trajectory(bad, expected).passed is False


def test_p0_failure_caps_an_otherwise_high_harness_score() -> None:
    cases = [
        HarnessEvaluationCase(id="contracts", dimension="contracts", passed=False, p0=True, detail="blocked tool executed"),
        HarnessEvaluationCase(id="loop", dimension="loop_recovery", passed=True, detail="recovery works"),
        HarnessEvaluationCase(id="cross", dimension="cross_domain", passed=True, detail="generic notes work"),
        HarnessEvaluationCase(id="bidpilot", dimension="bidpilot", passed=True, detail="runtime works"),
        HarnessEvaluationCase(id="graph", dimension="langgraph", passed=True, detail="graph works"),
    ]

    report = score_harness_cases(cases)

    assert report.raw_score == 65
    assert report.engineering_score == 59
    assert report.p0_failures == ("contracts",)
