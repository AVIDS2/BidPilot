import json
import hashlib
from pathlib import Path
import subprocess
import sys

from app.evaluation.bidbench import (
    BidBenchThresholds,
    apply_thresholds,
    check_thresholds,
    evaluate_files,
    render_markdown,
    write_report,
)


REPO_ROOT = Path(__file__).resolve().parents[4]


def _write_fixture_files(tmp_path: Path) -> tuple[Path, Path]:
    dataset_path = tmp_path / "dataset.json"
    candidate_path = tmp_path / "candidate.json"
    source_path = tmp_path / "rfp.md"
    source_path.write_text("Requirement one", encoding="utf-8")
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
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
                    {"id": "rfp", "path": "rfp.md", "title": "RFP", "source_type": "tender", "sha256": source_hash}
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
                "provenance": {
                    "evidence_set_id": "release-evidence-1",
                    "capture_id": "bidbench-capture-1",
                    "capture_kind": "current_pipeline",
                    "review_level": "two_person_review",
                    "evaluator_version": "bidpilot-evaluation-v1",
                    "attestation_ref": "ci:build-123",
                },
                "requirements": [
                    {
                        "id": "candidate-req-1",
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
    assert len(report.dataset_sha256) == 64
    assert len(report.candidate_sha256) == 64
    assert report.provenance is not None
    assert report.provenance.evidence_set_id == "release-evidence-1"
    assert report.source_hashes["rfp"] == hashlib.sha256(
        (tmp_path / "rfp.md").read_bytes()
    ).hexdigest()
    assert "BidBench Report" in markdown
    assert "100.00%" in markdown
    assert json.loads(json_path.read_text(encoding="utf-8"))["formula_version"] == "2.1"
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

    gated_report = apply_thresholds(
        report,
        BidBenchThresholds(min_mandatory_recall=0.95, min_combined_score=0.8),
    )
    assert gated_report.gate is not None
    assert gated_report.gate.passed is False
    assert gated_report.gate.failures == failures


def test_claim_trace_integrity_threshold_rejects_an_unscorable_candidate(tmp_path: Path) -> None:
    dataset_path, candidate_path = _write_fixture_files(tmp_path)
    report = evaluate_files(dataset_path, candidate_path)

    failures = check_thresholds(
        report,
        BidBenchThresholds(min_claim_trace_integrity_rate=1.0),
    )

    assert failures == [
        "claim_trace_integrity_rate is unavailable but requires minimum 1.0000"
    ]


def test_evaluate_files_rejects_source_hash_mismatch(tmp_path: Path) -> None:
    dataset_path, candidate_path = _write_fixture_files(tmp_path)
    (tmp_path / "rfp.md").write_text("tampered", encoding="utf-8")

    try:
        evaluate_files(dataset_path, candidate_path)
    except ValueError as exc:
        assert "sha256" in str(exc)
    else:
        raise AssertionError("tampered source must fail evaluation")


def test_snapshot_mode_archives_normalized_candidate(tmp_path: Path) -> None:
    dataset_path, _candidate_path = _write_fixture_files(tmp_path)
    snapshot_path = tmp_path / "requirements.json"
    trace_map_path = tmp_path / "trace-map.json"
    output_dir = tmp_path / "reports"
    snapshot_path.write_text(
        json.dumps(
            {
                "requirements": [
                    {
                        "id": "platform-req-1",
                        "project_id": "project-1",
                        "section_key": "scope",
                        "requirement_text": "requirement one",
                        "source_document_id": "source-db-1",
                        "source_locator_json": {"section": "1"},
                        "bid_profile": {
                            "bid_category": "mandatory",
                            "is_mandatory": True,
                            "coverage_status": "covered",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    trace_map_path.write_text(
        json.dumps({"source_document_ids": {"source-db-1": "rfp"}}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_bidbench.py"),
            "--dataset",
            str(dataset_path),
            "--requirements-snapshot",
            str(snapshot_path),
            "--trace-map",
            str(trace_map_path),
            "--candidate-id",
            "current-project-1",
            "--output-dir",
            str(output_dir),
            "--informational",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    candidate_paths = list(output_dir.rglob("candidate.json"))
    assert len(candidate_paths) == 1
    candidate = json.loads(candidate_paths[0].read_text(encoding="utf-8"))
    assert candidate["candidate_id"] == "current-project-1"
    assert candidate["requirements"][0]["locators"][0]["source_id"] == "rfp"
    assert (candidate_paths[0].parent / "report.json").is_file()
    assert (candidate_paths[0].parent / "report.md").is_file()
