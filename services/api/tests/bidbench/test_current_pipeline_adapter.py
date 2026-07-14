import json
from pathlib import Path

from app.evaluation.adapters import build_candidate_from_requirement_snapshot


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
