"""Agent web-source import stays bounded, durable, and retryable."""

from __future__ import annotations

import uuid

import pytest

from app.assistant.tools import fetch_url_to_project_tool
from app.auth.schemas import CurrentUser
from app.documents.import_errors import RemoteImportError
from app.documents.service import upload_artifact_file_command
from app.documents.web_import import (
    MAX_WEB_IMPORT_ARTIFACT_BYTES,
    MAX_WEB_IMPORT_ARTIFACT_SECONDS,
    MAX_WEB_IMPORT_BYTES,
    MAX_WEB_IMPORT_SECONDS,
    DownloadedWebSource,
    discover_remote_documents,
    download_web_source,
)
from app.models import Bundle, Project, ProjectMember, RuntimeEvent, RuntimeRun, SourceDocument
from app.runtime.service import create_runtime_run


def _user(default_org_id: str, default_user_id: str) -> CurrentUser:
    return CurrentUser(
        id=default_user_id,
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=default_org_id,
    )


def _project(test_db, default_org_id: str, default_user_id: str) -> Project:
    suffix = uuid.uuid4().hex[:8]
    project = Project(
        org_id=default_org_id,
        slug=f"web-import-{suffix}",
        name=f"Web import {suffix}",
        scenario_package="bidpilot",
    )
    test_db.add(project)
    test_db.flush()
    test_db.add(ProjectMember(project_id=project.id, user_id=default_user_id, role="owner"))
    test_db.commit()
    return project


def _downloaded() -> DownloadedWebSource:
    return DownloadedWebSource(
        data=b"# Tender notice\n\nThe supplier shall provide an implementation plan.",
        content_type="text/markdown",
        filename="tender-notice.md",
        source_url="https://buyer.example.test/notices/42",
    )


def _downloaded_zip() -> DownloadedWebSource:
    return DownloadedWebSource(
        data=b"PK\x03\x04tender-software",
        content_type="application/zip",
        filename="tender-software.zip",
        source_url="https://buyer.example.test/files/tender-software.zip",
    )


def test_agent_web_import_queues_durable_ingestion(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    user = _user(default_org_id, default_user_id)
    project = _project(test_db, default_org_id, default_user_id)
    queued: list[tuple[str, list[str]]] = []
    monkeypatch.setattr("app.documents.web_import.download_web_source", lambda *_args, **_kwargs: _downloaded())
    monkeypatch.setattr(
        "app.adapters.storage.upload_bytes",
        lambda project_id, object_name, _data, _mime_type: f"docpilot-{project_id}/{object_name}",
    )
    monkeypatch.setattr(
        "app.documents.service.celery.send_task",
        lambda name, args: queued.append((name, args)),
    )

    result = fetch_url_to_project_tool(
        test_db,
        user,
        {
            "project_id": project.id,
            "url": "https://buyer.example.test/notices/42",
            "import_mode": "web_evidence",
        },
    )

    assert result.result["ingest_queued"] is True
    assert result.result["source_url"] == "https://buyer.example.test/notices/42"
    assert result.result["bundle_label"] == "Agent uploads"
    assert queued == [("worker.ingest_bundle", [result.result["bundle_id"]])]
    document = test_db.get(SourceDocument, result.result["document_id"])
    bundle = test_db.get(Bundle, result.result["bundle_id"])
    assert document is not None and document.source_url == "https://buyer.example.test/notices/42"
    assert bundle is not None and bundle.ingest_status == "queued"


def test_agent_web_import_keeps_source_retryable_when_dispatch_is_down(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    user = _user(default_org_id, default_user_id)
    project = _project(test_db, default_org_id, default_user_id)
    monkeypatch.setattr("app.documents.web_import.download_web_source", lambda *_args, **_kwargs: _downloaded())
    monkeypatch.setattr(
        "app.adapters.storage.upload_bytes",
        lambda project_id, object_name, _data, _mime_type: f"docpilot-{project_id}/{object_name}",
    )

    def _unavailable(*_args, **_kwargs) -> None:
        raise OSError("broker unavailable")

    monkeypatch.setattr("app.documents.service.celery.send_task", _unavailable)

    result = fetch_url_to_project_tool(
        test_db,
        user,
        {
            "project_id": project.id,
            "url": "https://buyer.example.test/notices/42",
            "import_mode": "web_evidence",
        },
    )

    assert result.result["ingest_queued"] is False
    bundle = test_db.get(Bundle, result.result["bundle_id"])
    assert bundle is not None and bundle.ingest_status == "ready_to_ingest"


def test_agent_zip_import_stores_a_downloadable_artifact_without_queueing_parser(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    user = _user(default_org_id, default_user_id)
    project = _project(test_db, default_org_id, default_user_id)
    queued: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        "app.documents.web_import.download_web_source",
        lambda *_args, **_kwargs: _downloaded_zip(),
    )
    monkeypatch.setattr(
        "app.adapters.storage.upload_bytes",
        lambda project_id, object_name, _data, _mime_type: f"docpilot-{project_id}/{object_name}",
    )
    monkeypatch.setattr(
        "app.documents.service.celery.send_task",
        lambda name, args: queued.append((name, args)),
    )

    result = fetch_url_to_project_tool(
        test_db,
        user,
        {
            "project_id": project.id,
            "url": "https://buyer.example.test/files/tender-software.zip",
            "import_mode": "artifact",
        },
    )

    assert result.result["ingest_queued"] is False
    assert result.result["storage_status"] == "stored_no_parse"
    assert queued == []
    document = test_db.get(SourceDocument, result.result["document_id"])
    bundle = test_db.get(Bundle, result.result["bundle_id"])
    assert document is not None
    assert document.parse_status == "not_applicable"
    assert document.index_status == "not_applicable"
    assert bundle is not None and bundle.ingest_status == "ingested"


def test_agent_artifact_import_is_queued_as_a_child_runtime_run(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    user = _user(default_org_id, default_user_id)
    project = _project(test_db, default_org_id, default_user_id)
    parent = create_runtime_run(
        test_db,
        user,
        kind="assistant_turn",
        engine="test_harness",
        project_id=project.id,
    )
    queued: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        "app.celery_client.celery.send_task",
        lambda name, args: queued.append((name, args)),
    )

    result = fetch_url_to_project_tool(
        test_db,
        user,
        {
            "project_id": project.id,
            "url": "http://zfcg.example.test/files/tender-software.zip",
            "import_mode": "artifact",
            "parent_runtime_run_id": parent.id,
        },
    )

    assert result.result["status"] == "queued"
    assert result.result["runtime_run_id"]
    assert queued == [("worker.import_remote_document", [result.result["runtime_run_id"]])]
    child = test_db.get(RuntimeRun, result.result["runtime_run_id"])
    assert child is not None
    assert child.kind == "remote_import"
    assert child.parent_run_id == parent.id
    linked_event = test_db.scalar(
        test_db.query(RuntimeEvent)
        .filter(RuntimeEvent.run_id == parent.id, RuntimeEvent.event_type == "workflow.linked")
        .order_by(RuntimeEvent.sequence.desc())
        .limit(1)
        .statement
    )
    assert linked_event is not None
    assert linked_event.payload_json["workflow_runtime_run_id"] == child.id
    assert linked_event.payload_json["remote_import_runtime_run_id"] == child.id
    assert (
        test_db.query(SourceDocument)
        .filter(SourceDocument.source_url == "http://zfcg.example.test/files/tender-software.zip")
        .count()
        == 0
    )


def test_streamed_artifact_file_is_stored_without_loading_the_full_file(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
    tmp_path,
) -> None:
    user = _user(default_org_id, default_user_id)
    project = _project(test_db, default_org_id, default_user_id)
    bundle = Bundle(
        project_id=project.id,
        label="Agent uploads",
        source_type="agent",
        ingest_status="ready_to_ingest",
    )
    test_db.add(bundle)
    test_db.commit()
    local_file = tmp_path / "tender-software.zip"
    local_file.write_bytes(b"PK\x03\x04streamed-artifact")
    uploaded: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        "app.adapters.storage.upload_file",
        lambda project_id, object_name, file_path, _mime_type: (
            uploaded.append((project_id, object_name, file_path)) or f"docpilot-{project_id}/{object_name}"
        ),
    )

    result = upload_artifact_file_command(
        test_db,
        bundle_id=bundle.id,
        filename="tender-software.zip",
        content_type="application/zip",
        file_path=str(local_file),
        byte_count=local_file.stat().st_size,
        checksum="b" * 64,
        signature=b"PK\x03\x04streamed-artifact",
        current_user=user,
        source_url="https://buyer.example.test/files/tender-software.zip",
    )

    assert result.parse_status == "not_applicable"
    assert result.index_status == "not_applicable"
    assert len(uploaded) == 1
    assert uploaded[0][0] == project.id
    assert uploaded[0][2] == str(local_file)
    stored = test_db.get(SourceDocument, result.id)
    assert stored is not None
    assert stored.source_url == "https://buyer.example.test/files/tender-software.zip"
    assert test_db.get(Bundle, bundle.id).ingest_status == "ingested"


def test_artifact_import_rejects_a_webpage(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.documents.web_import._fetch_remote_resource",
        lambda *_args, **_kwargs: (b"<!doctype html><html><body>notice</body></html>", "text/html", "https://buyer.example.test/notice"),
    )

    with pytest.raises(RemoteImportError, match="网页而不是可下载附件") as exc_info:
        download_web_source("https://buyer.example.test/notice")

    assert exc_info.value.error_code == "remote_not_artifact"


def test_remote_import_uses_artifact_limit_without_relaxing_web_evidence(monkeypatch) -> None:
    captured: list[tuple[int, float]] = []

    def _fetch(*_args, **kwargs):
        captured.append((kwargs["max_bytes"], kwargs["max_seconds"]))
        return b"PK\x03\x04artifact", "application/zip", "https://buyer.example.test/file.zip"

    monkeypatch.setattr(
        "app.documents.web_import._fetch_remote_resource",
        _fetch,
    )

    download_web_source("https://buyer.example.test/file.zip", import_mode="artifact")
    download_web_source("https://buyer.example.test/notice", import_mode="web_evidence")

    assert captured == [
        (MAX_WEB_IMPORT_ARTIFACT_BYTES, MAX_WEB_IMPORT_ARTIFACT_SECONDS),
        (MAX_WEB_IMPORT_BYTES, MAX_WEB_IMPORT_SECONDS),
    ]


def test_discover_remote_documents_returns_direct_links_without_persisting(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.documents.web_import._fetch_remote_resource",
        lambda *_args, **_kwargs: (
            """
            <html><body>
              <a href='/files/tender.pdf'>招标文件下载</a>
              <a href='/files/appendix.docx'>技术附件</a>
              <a href='/notice/42'>公告正文</a>
              <a href='/notice/42/details'>查看详情</a>
            </body></html>
            """.encode("utf-8"),
            "text/html",
            "https://buyer.example.test/notices/42",
        ),
    )

    candidates = discover_remote_documents("https://buyer.example.test/notices/42")

    assert [candidate.filename for candidate in candidates] == ["tender.pdf", "appendix.docx"]
    assert candidates[0].url == "https://buyer.example.test/files/tender.pdf"
