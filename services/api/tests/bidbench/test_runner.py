import json
from pathlib import Path

from app.evaluation.bidbench import (
    BidBenchThresholds,
    check_thresholds,
    evaluate_files,
    render_markdown,
    write_report,
)


def _write_fixture_files(tmp_path: Path) -> tuple[Path, Path]:
    dataset_path = tmp_path / "dataset.json"
    candidate_path = tmp_path / "candidate.json"
    dataset_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "dataset_id": "runner-fixture",
                "title": "Runner fixture",
                "language": "en",
                "dataset_role": "development",
                "origin_type": "synthetic",
                "provenance": "Unit test",
                "license_id": "CC0-1.0",
                "sources": [
                    {"id": "rfp", "path": "rfp.md", "title": "RFP", "source_type": "tender"}
                ],
                "requirements": [
                    {
                        "id": "req-1",
                        "original_text": "Requirement one",
                        "normalized_text": "requirement one",
                        "requirement_type": "mandatory",
                        "is_mandatory": True,
                        "expected_coverage": "covered",
                        "locators": [{"source_id": "rfp", "section": "1"}],
                        "expected_evidence_ids": [],
                    }
                ],
                "evidence": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    candidate_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "dataset_id": "runner-fixture",
                "candidate_id": "candidate-1",
                "system_name": "unit-test",
                "requirements": [
                    {
                        "id": "candidate-req-1",
                        "ground_truth_id": "req-1",
                        "normalized_text": "requirement one",
                        "requirement_type": "mandatory",
                        "is_mandatory": True,
                        "coverage_status": "covered",
                        "locators": [{"source_id": "rfp", "section": "1"}],
                        "evidence_ids": [],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return dataset_path, candidate_path


def test_evaluate_files_and_write_reports(tmp_path: Path) -> None:
    dataset_path, candidate_path = _write_fixture_files(tmp_path)

    report = evaluate_files(dataset_path, candidate_path)
    markdown = render_markdown(report)
    json_path, markdown_path = write_report(report, tmp_path / "output")

    assert report.dataset_id == "runner-fixture"
    assert report.metrics.combined_score == 1
    assert "BidBench Report" in markdown
    assert "100.00%" in markdown
    assert json.loads(json_path.read_text(encoding="utf-8"))["formula_version"] == "1.0"
    assert markdown_path.read_text(encoding="utf-8") == markdown


def test_threshold_check_returns_actionable_failures(tmp_path: Path) -> None:
    dataset_path, candidate_path = _write_fixture_files(tmp_path)
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate["requirements"] = []
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
    report = evaluate_files(dataset_path, candidate_path)

    failures = check_thresholds(
        report,
        BidBenchThresholds(
            min_mandatory_recall=0.95,
            min_combined_score=0.8,
        ),
    )

    assert any("mandatory_recall" in failure for failure in failures)
    assert any("combined_score" in failure for failure in failures)
