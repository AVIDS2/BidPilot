import json
from pathlib import Path

from app.evaluation.adapters import (
    CurrentPipelineTraceMap,
    build_candidate_from_requirement_snapshot,
)


def test_current_requirement_snapshot_converts_to_candidate(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "requirements.json"
    snapshot_path.write_text(
        json.dumps(
            [
                {
                    "id": "platform-req-1",
                    "project_id": "project-1",
                    "section_key": "security",
                    "requirement_text": "系统必须支持角色权限控制",
                    "priority": "high",
                    "status": "confirmed",
                },
                {
                    "id": "platform-req-2",
                    "project_id": "project-1",
                    "section_key": "operations",
                    "requirement_text": "提供运行报告",
                    "priority": "normal",
                    "status": "draft",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    candidate = build_candidate_from_requirement_snapshot(
        snapshot_path=snapshot_path,
        dataset_id="demo-smart-community",
        candidate_id="current-project-1",
        git_commit="abc1234",
    )

    assert candidate.system_name == "bidpilot-current-requirement-api"
    assert candidate.git_commit == "abc1234"
    assert len(candidate.requirements) == 2
    assert candidate.requirements[0].is_mandatory is True
    assert candidate.requirements[0].requirement_type == "mandatory"
    assert candidate.requirements[0].coverage_status == "uncovered"
    assert candidate.requirements[1].is_mandatory is False
    assert candidate.requirements[1].requirement_type == "technical"


def test_current_requirement_snapshot_accepts_wrapped_api_response(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "requirements.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "requirements": [
                    {
                        "id": "platform-req-1",
                        "project_id": "project-1",
                        "section_key": "scope",
                        "requirement_text": "Provide implementation plan",
                        "priority": "low",
                        "status": "draft",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    candidate = build_candidate_from_requirement_snapshot(
        snapshot_path=snapshot_path,
        dataset_id="fixture",
        candidate_id="wrapped",
    )

    assert [item.id for item in candidate.requirements] == ["platform-req-1"]


def test_current_requirement_snapshot_rejects_error_response(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "error.json"
    snapshot_path.write_text(json.dumps({"detail": "Unauthorized"}), encoding="utf-8")

    try:
        build_candidate_from_requirement_snapshot(
            snapshot_path=snapshot_path,
            dataset_id="fixture",
            candidate_id="error",
        )
    except ValueError as exc:
        assert "requirements" in str(exc)
    else:
        raise AssertionError("error response must not become an empty candidate")


def test_current_requirement_snapshot_rejects_multiple_projects(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "mixed.json"
    snapshot_path.write_text(
        json.dumps(
            [
                {"id": "1", "project_id": "a", "section_key": "x", "requirement_text": "one"},
                {"id": "2", "project_id": "b", "section_key": "x", "requirement_text": "two"},
            ]
        ),
        encoding="utf-8",
    )

    try:
        build_candidate_from_requirement_snapshot(
            snapshot_path=snapshot_path,
            dataset_id="fixture",
            candidate_id="mixed",
        )
    except ValueError as exc:
        assert "multiple projects" in str(exc)
    else:
        raise AssertionError("mixed-project snapshots must be rejected")


def test_current_requirement_detail_snapshot_preserves_mapped_traceability(
    tmp_path: Path,
) -> None:
    snapshot_path = tmp_path / "requirement-details.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "requirements": [
                    {
                        "id": "platform-req-1",
                        "project_id": "project-1",
                        "section_key": "qualification",
                        "requirement_text": "提供有效的信息安全管理体系认证",
                        "priority": "normal",
                        "source_document_id": "source-db-1",
                        "source_locator_json": {
                            "section": "3.2 资格要求",
                            "text_anchor": "信息安全管理体系认证",
                        },
                        "extraction_confidence": 0.97,
                        "bid_profile": {
                            "bid_category": "qualification",
                            "is_mandatory": True,
                            "coverage_status": "covered",
                        },
                        "evidence_links": [
                            {
                                "id": "link-db-1",
                                "requirement_id": "platform-req-1",
                                "evidence_id": "evidence-db-1",
                                "relation_type": "supports",
                            }
                        ],
                        "claims": [
                            {
                                "id": "claim-db-1",
                                "project_id": "project-1",
                                "requirement_id": "platform-req-1",
                                "claim_text": "我方已通过信息安全管理体系认证。",
                                "claim_type": "factual",
                                "status": "verified",
                                "evidence_ids": ["evidence-db-1"],
                            }
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    candidate = build_candidate_from_requirement_snapshot(
        snapshot_path=snapshot_path,
        dataset_id="demo-smart-community",
        candidate_id="current-project-1",
        trace_map=CurrentPipelineTraceMap(
            source_document_ids={"source-db-1": "rfp"},
            evidence_ids={"evidence-db-1": "ev-001"},
        ),
    )

    requirement = candidate.requirements[0]
    assert requirement.requirement_type == "qualification"
    assert requirement.is_mandatory is True
    assert requirement.coverage_status == "covered"
    assert requirement.confidence == 0.97
    assert requirement.locators[0].source_id == "rfp"
    assert requirement.evidence_ids == ["ev-001"]
    assert candidate.claims[0].accepted is True
    assert candidate.claims[0].requirement_ids == ["platform-req-1"]
    assert candidate.claims[0].evidence_ids == ["ev-001"]


def test_current_requirement_detail_snapshot_does_not_invent_unmapped_traceability(
    tmp_path: Path,
) -> None:
    snapshot_path = tmp_path / "unmapped-details.json"
    snapshot_path.write_text(
        json.dumps(
            [
                {
                    "id": "platform-req-1",
                    "project_id": "project-1",
                    "section_key": "security",
                    "requirement_text": "支持访问控制",
                    "source_document_id": "source-db-1",
                    "source_locator_json": {"section": "3.5 权限与安全"},
                    "bid_profile": {
                        "bid_category": "technical",
                        "coverage_status": "partial",
                    },
                    "evidence_links": [
                        {
                            "id": "link-db-1",
                            "requirement_id": "platform-req-1",
                            "evidence_id": "evidence-db-1",
                            "relation_type": "supports",
                        }
                    ],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    candidate = build_candidate_from_requirement_snapshot(
        snapshot_path=snapshot_path,
        dataset_id="demo-smart-community",
        candidate_id="unmapped",
    )

    assert candidate.requirements[0].locators == []
    assert candidate.requirements[0].evidence_ids == []
