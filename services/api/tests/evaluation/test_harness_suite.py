"""Prevent the harness evaluation matrix from silently losing a dimension."""

from app.evaluation.harness_suite import HARNESS_EVALUATION_TARGETS


def test_harness_suite_covers_every_weighted_dimension_with_unique_cases() -> None:
    ids = [target.id for target in HARNESS_EVALUATION_TARGETS]
    dimensions = {target.dimension for target in HARNESS_EVALUATION_TARGETS}

    assert len(ids) == len(set(ids))
    assert dimensions == {"contracts", "loop_recovery", "cross_domain", "bidpilot", "langgraph"}
    assert any(target.p0 for target in HARNESS_EVALUATION_TARGETS)
