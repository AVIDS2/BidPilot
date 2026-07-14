import pytest
from pydantic import ValidationError

from contracts import BidBenchCandidate, BidBenchDataset


def _valid_dataset() -> dict:
    return {
        "schema_version": "1.0",
        "dataset_id": "demo-smart-community",
        "title": "Smart community technical bid",
        "language": "zh-CN",
        "dataset_role": "development",
        "origin_type": "synthetic",
        "provenance": "Created for BidPilot benchmark development.",
        "license_id": "CC0-1.0",
        "sources": [
            {
                "id": "rfp",
                "path": "sources/01-rfp.md",
                "title": "Tender document",
                "source_type": "tender",
            },
            {
                "id": "supplier",
                "path": "sources/02-supplier.md",
                "title": "Supplier profile",
                "source_type": "supplier_evidence",
            },
        ],
        "requirements": [
            {
                "id": "req-001",
                "original_text": "投标人须提供信息安全管理体系认证。",
                "normalized_text": "提供有效的信息安全管理体系认证",
                "requirement_type": "qualification",
                "is_mandatory": True,
                "expected_coverage": "covered",
                "locators": [
                    {
                        "source_id": "rfp",
                        "section": "3.2 资格要求",
                        "text_anchor": "信息安全管理体系认证",
                    }
                ],
                "expected_evidence_ids": ["ev-001"],
            }
        ],
        "evidence": [
            {
                "id": "ev-001",
                "source_id": "supplier",
                "text": "已通过 ISO/IEC 27001 信息安全管理体系认证。",
                "locator": {
                    "source_id": "supplier",
                    "section": "企业资质",
                    "text_anchor": "ISO/IEC 27001",
                },
                "supports_requirement_ids": ["req-001"],
            }
        ],
    }


def test_bidbench_dataset_accepts_valid_references() -> None:
    dataset = BidBenchDataset.model_validate(_valid_dataset())

    assert dataset.schema_version == "1.0"
    assert dataset.requirements[0].expected_coverage == "covered"
    assert dataset.evidence[0].supports_requirement_ids == ["req-001"]


def test_contracts_package_exports_bidbench_models() -> None:
    assert BidBenchDataset.__name__ == "BidBenchDataset"
    assert BidBenchCandidate.__name__ == "BidBenchCandidate"


@pytest.mark.parametrize("collection", ["sources", "requirements", "evidence"])
def test_bidbench_dataset_rejects_duplicate_ids(collection: str) -> None:
    payload = _valid_dataset()
    payload[collection].append(dict(payload[collection][0]))

    with pytest.raises(ValidationError, match="duplicate"):
        BidBenchDataset.model_validate(payload)


def test_bidbench_dataset_rejects_unknown_source_reference() -> None:
    payload = _valid_dataset()
    payload["requirements"][0]["locators"][0]["source_id"] = "missing-source"

    with pytest.raises(ValidationError, match="unknown source"):
        BidBenchDataset.model_validate(payload)


def test_bidbench_dataset_rejects_unknown_evidence_reference() -> None:
    payload = _valid_dataset()
    payload["requirements"][0]["expected_evidence_ids"] = ["missing-evidence"]

    with pytest.raises(ValidationError, match="unknown evidence"):
        BidBenchDataset.model_validate(payload)


def test_bidbench_dataset_rejects_unknown_requirement_reference() -> None:
    payload = _valid_dataset()
    payload["evidence"][0]["supports_requirement_ids"] = ["missing-requirement"]

    with pytest.raises(ValidationError, match="unknown requirement"):
        BidBenchDataset.model_validate(payload)


def test_mandatory_requirement_requires_a_source_locator() -> None:
    payload = _valid_dataset()
    payload["requirements"][0]["locators"] = []

    with pytest.raises(ValidationError, match="mandatory requirement"):
        BidBenchDataset.model_validate(payload)


def test_locator_requires_a_position_hint() -> None:
    payload = _valid_dataset()
    payload["requirements"][0]["locators"] = [{"source_id": "rfp"}]

    with pytest.raises(ValidationError, match="position hint"):
        BidBenchDataset.model_validate(payload)


def test_dataset_rejects_unknown_coverage_state() -> None:
    payload = _valid_dataset()
    payload["requirements"][0]["expected_coverage"] = "probably-covered"

    with pytest.raises(ValidationError):
        BidBenchDataset.model_validate(payload)


def test_candidate_output_accepts_versioned_saved_result() -> None:
    candidate = BidBenchCandidate.model_validate(
        {
            "schema_version": "1.0",
            "dataset_id": "demo-smart-community",
            "candidate_id": "current-pipeline-run-001",
            "system_name": "current-pipeline",
            "git_commit": "abc1234",
            "prompt_version": "requirements-v1",
            "run_number": 1,
            "requirements": [
                {
                    "id": "candidate-req-001",
                    "normalized_text": "提供有效的信息安全管理体系认证",
                    "requirement_type": "qualification",
                    "is_mandatory": True,
                    "coverage_status": "covered",
                    "locators": [
                        {
                            "source_id": "rfp",
                            "section": "3.2 资格要求",
                            "text_anchor": "信息安全管理体系认证",
                        }
                    ],
                    "evidence_ids": ["ev-001"],
                }
            ],
        }
    )

    assert candidate.system_name == "current-pipeline"
    assert candidate.requirements[0].coverage_status == "covered"


def test_candidate_output_rejects_duplicate_requirement_ids() -> None:
    payload = {
        "schema_version": "1.0",
        "dataset_id": "demo-smart-community",
        "candidate_id": "duplicate-run",
        "system_name": "fixture",
        "requirements": [
            {
                "id": "candidate-req-001",
                "normalized_text": "Requirement one",
                "requirement_type": "mandatory",
                "is_mandatory": True,
                "coverage_status": "uncovered",
                "locators": [{"source_id": "rfp", "section": "1"}],
            },
            {
                "id": "candidate-req-001",
                "normalized_text": "Requirement two",
                "requirement_type": "technical",
                "is_mandatory": False,
                "coverage_status": "partial",
                "locators": [{"source_id": "rfp", "section": "2"}],
            },
        ],
    }

    with pytest.raises(ValidationError, match="duplicate"):
        BidBenchCandidate.model_validate(payload)
