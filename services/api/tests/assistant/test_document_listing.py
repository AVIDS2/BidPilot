from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.assistant.tools import _normalize_readiness_gap_kind, list_documents_tool
from app.auth.schemas import CurrentUser


def test_list_documents_without_bundle_id_reads_all_project_bundles() -> None:
    user = CurrentUser(
        id="user-1",
        email="user@example.test",
        display_name="Test User",
        role="member",
        org_id="org-1",
    )
    bundles = [
        SimpleNamespace(id="bundle-1", label="招标文件", ingest_status="indexed"),
        SimpleNamespace(id="bundle-2", label="补充资料", ingest_status="queued"),
    ]
    documents = {
        "bundle-1": [
            SimpleNamespace(
                model_dump=lambda: {
                    "id": "doc-1",
                    "original_filename": "招标文件.pdf",
                    "parse_status": "parsed",
                    "index_status": "indexed",
                }
            )
        ],
        "bundle-2": [],
    }

    with (
        patch("app.assistant.tools._get_project_for_user", return_value=SimpleNamespace(id="project-1")),
        patch("app.assistant.tools.list_bundles_query", return_value=bundles),
        patch("app.assistant.tools.list_documents_query", side_effect=lambda _db, bundle_id, _user: documents[bundle_id]),
    ):
        result = list_documents_tool(Mock(), user, {"project_id": "project-1"})

    assert result.summary == "找到 1 个文档。"
    assert result.result["items"] == [
        {
            "id": "doc-1",
            "original_filename": "招标文件.pdf",
            "parse_status": "parsed",
            "index_status": "indexed",
            "bundle_label": "招标文件",
            "bundle_status": "indexed",
        }
    ]


def test_readiness_gap_kind_accepts_requirement_aliases() -> None:
    assert _normalize_readiness_gap_kind("requirement") == "mandatory"
    assert _normalize_readiness_gap_kind("evidence_gaps") == "evidence"
    assert _normalize_readiness_gap_kind("unknown") == "all"
