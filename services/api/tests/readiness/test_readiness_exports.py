from io import BytesIO

from docx import Document
from openpyxl import load_workbook

from app.readiness.exporters import render_readiness_docx, render_readiness_xlsx
from app.readiness.schemas import BidReadinessSummary


def _summary() -> BidReadinessSummary:
    return BidReadinessSummary.model_validate(
        {
            "formula_version": "1.0",
            "project_id": "project-1",
            "project_name": "Example Bid",
            "generated_at": "2026-07-14T10:00:00Z",
            "source_fingerprint": "a" * 64,
            "score_label": "response_readiness",
            "readiness_score": 72.5,
            "counts": {
                "total": 2,
                "mandatory": 1,
                "scored": 1,
                "covered": 1,
                "partial": 0,
                "uncovered": 1,
                "disputed": 0,
                "not_applicable": 0,
                "accepted_risk": 0,
                "verified": 1,
                "assigned": 1,
            },
            "scores": {
                "mandatory_closure": 0.5,
                "scored_coverage": 1.0,
                "verification": 0.5,
                "assignment": 0.5,
            },
            "requirements": [
                {
                    "id": "req-1",
                    "section_key": "security",
                    "requirement_text": "Provide ISO 27001",
                    "bid_category": "qualification",
                    "is_mandatory": True,
                    "score_weight": None,
                    "risk_level": "high",
                    "coverage_status": "uncovered",
                    "evidence_status": "missing",
                    "verification_status": "unverified",
                    "owner_user_id": None,
                    "reviewer_user_id": None,
                    "due_at": None,
                    "source_locator_json": {"section": "3.2"},
                },
                {
                    "id": "req-2",
                    "section_key": "architecture",
                    "requirement_text": "Architecture score",
                    "bid_category": "scored",
                    "is_mandatory": False,
                    "score_weight": 10,
                    "risk_level": "normal",
                    "coverage_status": "covered",
                    "evidence_status": "sufficient",
                    "verification_status": "verified",
                    "owner_user_id": "user-1",
                    "reviewer_user_id": None,
                    "due_at": None,
                    "source_locator_json": {"section": "7.2"},
                },
            ],
            "mandatory_gaps": [],
            "evidence_gaps": [],
            "contradictions": [],
            "overdue": [],
            "qualifications": [],
            "workload": {"unassigned": 1, "by_owner": {"user-1": 1}},
        }
    )


def test_xlsx_export_contains_summary_and_requirement_matrix() -> None:
    data = render_readiness_xlsx(_summary())
    workbook = load_workbook(BytesIO(data), read_only=True)

    assert workbook.sheetnames == ["Summary", "Requirements"]
    assert workbook["Summary"]["A1"].value == "BidPilot Bid Readiness Pack"
    assert workbook["Requirements"]["A2"].value == "req-1"
    assert workbook["Requirements"]["H2"].value == "uncovered"


def test_docx_export_contains_executive_summary_and_gaps() -> None:
    data = render_readiness_docx(_summary())
    document = Document(BytesIO(data))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)

    assert "BidPilot Bid Readiness Pack" in text
    assert "Example Bid" in text
    assert "72.5" in text
