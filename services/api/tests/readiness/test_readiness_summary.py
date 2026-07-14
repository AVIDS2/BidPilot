import uuid

import pytest

from app.db import SessionLocal
from app.models import BidRequirementProfile, RequirementItem


def _create_project(client, name: str) -> str:
    response = client.post(
        "/projects",
        json={"name": name, "scenario_package": "bidpilot"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_readiness_summary_is_deterministic_and_not_win_probability(
    client,
    default_user_id: str,
) -> None:
    project_id = _create_project(client, "Readiness Summary Project")
    db = SessionLocal()
    try:
        fixtures = [
            ("Mandatory covered", True, None, "covered", "sufficient", "verified", default_user_id),
            ("Mandatory gap", True, None, "uncovered", "missing", "unverified", None),
            ("Scored partial", False, 10.0, "partial", "weak", "verified", default_user_id),
            ("Scored covered", False, 20.0, "covered", "sufficient", "unverified", None),
        ]
        for index, (
            text,
            mandatory,
            score_weight,
            coverage,
            evidence,
            verification,
            owner,
        ) in enumerate(fixtures):
            requirement = RequirementItem(
                id=str(uuid.uuid4()),
                project_id=project_id,
                section_key=f"section-{index}",
                requirement_text=text,
                verification_status=verification,
                owner_user_id=owner,
            )
            requirement.bid_profile = BidRequirementProfile(
                bid_category="qualification" if index < 2 else "scored",
                is_mandatory=mandatory,
                score_weight=score_weight,
                risk_level="high" if coverage == "uncovered" else "normal",
                coverage_status=coverage,
                evidence_status=evidence,
            )
            db.add(requirement)
        db.commit()
    finally:
        db.close()

    response = client.get(f"/readiness/projects/{project_id}")

    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["formula_version"] == "1.0"
    assert summary["readiness_score"] == pytest.approx(60.0)
    assert summary["score_label"] == "response_readiness"
    assert "win" not in summary["score_label"]
    assert summary["counts"]["total"] == 4
    assert summary["counts"]["mandatory"] == 2
    assert summary["counts"]["uncovered"] == 1
    assert summary["scores"]["mandatory_closure"] == 0.5
    assert summary["scores"]["scored_coverage"] == pytest.approx(5 / 6)
    assert summary["scores"]["verification"] == 0.5
    assert summary["scores"]["assignment"] == 0.5
    assert [item["requirement_text"] for item in summary["mandatory_gaps"]] == [
        "Mandatory gap"
    ]
    assert len(summary["source_fingerprint"]) == 64


def test_readiness_pack_is_versioned_stored_and_downloadable(
    client,
    default_user_id: str,
    monkeypatch,
) -> None:
    project_id = _create_project(client, "Readiness Artifact Project")
    uploads: dict[str, bytes] = {}

    def fake_upload(project: str, object_name: str, data: bytes, content_type: str) -> str:
        assert project == project_id
        assert content_type
        uploads[object_name] = data
        return f"bucket/{object_name}"

    def fake_download(project: str, object_name: str) -> bytes:
        assert project == project_id
        return uploads[object_name]

    monkeypatch.setattr("app.readiness.service.upload_bytes", fake_upload)
    monkeypatch.setattr("app.readiness.service.download_bytes", fake_download)

    first = client.post(f"/readiness/projects/{project_id}/packs")
    second = client.post(f"/readiness/projects/{project_id}/packs")

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["version_number"] == 1
    assert second.json()["version_number"] == 2
    assert first.json()["status"] == "generated"
    assert first.json()["xlsx_storage_key"].endswith("bid-readiness.xlsx")
    assert first.json()["docx_storage_key"].endswith("bid-readiness.docx")
    assert len(uploads) == 4

    downloaded = client.get(f"/readiness/packs/{first.json()['id']}/xlsx")
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content.startswith(b"PK")
    assert "bid-readiness-v1.xlsx" in downloaded.headers["content-disposition"]
