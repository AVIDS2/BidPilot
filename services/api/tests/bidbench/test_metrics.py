import pytest

from contracts import BidBenchCandidate, BidBenchDataset

from app.evaluation.metrics import score_candidate


def _dataset() -> BidBenchDataset:
    return BidBenchDataset.model_validate(
        {
            "schema_version": "1.0",
            "dataset_id": "metric-fixture",
            "title": "Metric fixture",
            "language": "en",
            "dataset_role": "development",
            "origin_type": "synthetic",
            "provenance": "Unit test",
            "license_id": "CC0-1.0",
            "sources": [
                {"id": "rfp", "path": "rfp.md", "title": "RFP", "source_type": "tender", "sha256": "a" * 64},
                {"id": "other", "path": "other.md", "title": "Other", "source_type": "supplier_evidence", "sha256": "b" * 64},
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
                    "expected_evidence_ids": ["ev-1"],
                },
                {
                    "id": "req-2",
                    "original_text": "Requirement two",
                    "normalized_text": "requirement two",
                    "requirement_type": "scored",
                    "is_mandatory": False,
                    "expected_coverage": "partial",
                    "locators": [{"source_id": "rfp", "section": "2"}],
                    "expected_evidence_ids": ["ev-2"],
                    "score_weight": 10,
                },
                {
                    "id": "req-3",
                    "original_text": "Requirement three",
                    "normalized_text": "requirement three",
                    "requirement_type": "technical",
                    "is_mandatory": False,
                    "expected_coverage": "uncovered",
                    "locators": [{"source_id": "rfp", "section": "3"}],
                    "expected_evidence_ids": [],
                },
            ],
            "evidence": [
                {
                    "id": "ev-1",
                    "source_id": "other",
                    "text": "Evidence one",
                    "locator": {"source_id": "other", "section": "A"},
                    "supports_requirement_ids": ["req-1"],
                },
                {
                    "id": "ev-2",
                    "source_id": "other",
                    "text": "Evidence two",
                    "locator": {"source_id": "other", "section": "B"},
                    "supports_requirement_ids": ["req-2"],
                },
            ],
        }
    )


def _candidate() -> BidBenchCandidate:
    return BidBenchCandidate.model_validate(
        {
            "schema_version": "1.0",
            "dataset_id": "metric-fixture",
            "candidate_id": "candidate-1",
            "system_name": "unit-test",
            "requirements": [
                {
                    "id": "cand-1",
                    "normalized_text": "Requirement one",
                    "requirement_type": "mandatory",
                    "is_mandatory": True,
                    "coverage_status": "covered",
                    "locators": [{"source_id": "rfp", "section": "1"}],
                    "evidence_ids": ["ev-1"],
                },
                {
                    "id": "cand-2",
                    "normalized_text": "Requirement two",
                    "requirement_type": "scored",
                    "is_mandatory": False,
                    "coverage_status": "partial",
                    "locators": [{"source_id": "other", "section": "2"}],
                    "evidence_ids": ["missing-evidence"],
                },
                {
                    "id": "cand-false-positive",
                    "normalized_text": "invented requirement",
                    "requirement_type": "technical",
                    "is_mandatory": False,
                    "coverage_status": "covered",
                    "locators": [{"source_id": "rfp", "section": "99"}],
                    "evidence_ids": ["invented-evidence"],
                },
            ],
            "claims": [
                {"id": "claim-1", "text": "Grounded", "evidence_ids": ["ev-1"]},
                {"id": "claim-2", "text": "Unsupported"},
                {"id": "claim-3", "text": "Inference", "is_inference": True},
            ],
        }
    )


def test_score_candidate_calculates_completeness_and_traceability() -> None:
    report = score_candidate(_dataset(), _candidate())

    assert report.counts.ground_truth_requirements == 3
    assert report.counts.candidate_requirements == 3
    assert report.counts.matched_requirements == 2
    assert report.requirement_recall == pytest.approx(2 / 3)
    assert report.requirement_precision == pytest.approx(2 / 3)
    assert report.requirement_f1 == pytest.approx(2 / 3)
    assert report.mandatory_recall == 1
    assert report.scored_recall == 1
    assert report.scored_weight_recall == 1
    assert report.classification_accuracy == 1
    assert report.coverage_accuracy == 1
    assert report.source_association_accuracy == 0.5
    assert report.evidence_precision == pytest.approx(1 / 3)
    assert report.evidence_recall == 0.5
    assert report.evidence_f1 == pytest.approx(0.4)
    assert report.unsupported_claim_rate == pytest.approx(1 / 3)
    assert report.claim_grounding_rate == pytest.approx(2 / 3)
    assert report.completeness_score == pytest.approx(14 / 15)
    assert report.traceability_score == pytest.approx(0.45)
    assert report.combined_score == pytest.approx(0.74)


def test_score_candidate_rejects_wrong_dataset() -> None:
    candidate = _candidate().model_copy(update={"dataset_id": "other-dataset"})

    with pytest.raises(ValueError, match="dataset_id"):
        score_candidate(_dataset(), candidate)


def test_candidate_cannot_self_declare_ground_truth_match() -> None:
    payload = _candidate().model_dump(mode="json")
    payload["requirements"][0]["normalized_text"] = "completely unrelated"
    candidate = BidBenchCandidate.model_validate(payload)

    report = score_candidate(_dataset(), candidate)

    assert report.counts.matched_requirements == 1
    assert report.mandatory_recall == 0


def test_source_accuracy_requires_a_real_position_match() -> None:
    payload = _candidate().model_dump(mode="json")
    payload["requirements"][0]["locators"] = [
        {"source_id": "rfp", "section": "invented section"}
    ]
    candidate = BidBenchCandidate.model_validate(payload)

    report = score_candidate(_dataset(), candidate)

    assert report.source_association_accuracy == 0


def test_unknown_evidence_id_does_not_ground_a_claim() -> None:
    payload = _candidate().model_dump(mode="json")
    payload["claims"] = [
        {"id": "claim-invalid", "text": "Fake grounding", "evidence_ids": ["does-not-exist"]}
    ]
    candidate = BidBenchCandidate.model_validate(payload)

    report = score_candidate(_dataset(), candidate)

    assert report.unsupported_claim_rate == 1
    assert report.claim_grounding_rate == 0
