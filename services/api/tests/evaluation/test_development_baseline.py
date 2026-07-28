from __future__ import annotations

import json
from pathlib import Path

from app.evaluation.development_baseline import (
    DEVELOPMENT_BASELINE_ID,
    MIN_DEVELOPMENT_BASELINE_CASES,
    build_development_baseline,
    render_development_baseline_markdown,
    write_development_baseline,
)


def _benchmark_root() -> Path:
    return (
        Path(__file__).resolve().parents[4]
        / "benchmarks"
        / "bidbench"
        / "v1"
        / "demo-smart-community"
    )


def test_development_baseline_covers_all_four_evaluators_with_fixed_case_metadata() -> None:
    result = build_development_baseline(_benchmark_root(), git_commit="a" * 40)

    receipt = result.receipt
    assert receipt.baseline_id == DEVELOPMENT_BASELINE_ID
    assert receipt.total_case_count == 63
    assert receipt.total_case_count >= MIN_DEVELOPMENT_BASELINE_CASES
    assert receipt.release_eligible is False
    assert {item.kind for item in receipt.reports} == {"bidbench", "retrieval", "memory", "assistant"}
    assert all(item.git_commit == "a" * 40 for item in receipt.reports)
    assert all(len(item.dataset_fingerprint) == 64 for item in receipt.reports)
    assert all(len(item.report_sha256) == 64 for item in receipt.reports)
    assert all(item.capture_kind == "control_fixture" for item in receipt.reports)
    assert result.assistant_report.capture_readiness.controlled_capture_ready is False
    assert "Release eligible: `false`" in render_development_baseline_markdown(receipt)


def test_development_baseline_writes_four_reports_and_one_aggregate_receipt(tmp_path: Path) -> None:
    result = build_development_baseline(_benchmark_root(), git_commit="b" * 40)
    outputs = write_development_baseline(result, tmp_path)

    assert set(outputs) == {
        "bidbench_json",
        "bidbench_markdown",
        "retrieval_json",
        "retrieval_markdown",
        "memory_json",
        "memory_markdown",
        "assistant_json",
        "assistant_markdown",
        "baseline_json",
        "baseline_markdown",
    }
    assert all(path.is_file() for path in outputs.values())
    payload = json.loads(outputs["baseline_json"].read_text(encoding="utf-8"))
    assert payload["total_case_count"] == 63
    assert payload["release_eligible"] is False
