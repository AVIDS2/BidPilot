from unittest.mock import patch


def _create_upload_bundle(client, name: str) -> tuple[str, str]:
    project = client.post(
        "/projects",
        json={"name": name, "scenario_package": "bidpilot"},
    )
    assert project.status_code == 201
    project_id = project.json()["id"]
    bundle = client.post(
        "/bundles",
        json={"project_id": project_id, "label": "RFP 资料包", "source_type": "upload"},
    )
    assert bundle.status_code == 201
    return project_id, bundle.json()["id"]


def test_upload_normalizes_type_and_creates_explicit_document_version(client) -> None:
    project_id, bundle_id = _create_upload_bundle(client, "Document Version Contract")

    with patch(
        "app.adapters.storage.upload_bytes",
        side_effect=lambda _project_id, object_name, _data, _mime_type: f"{project_id}/{object_name}",
    ):
        first = client.post(
            "/documents/upload",
            params={"bundle_id": bundle_id, "defer_ingest": True},
            files={"file": ("RFP.txt", b"\xe6\x8a\x95\xe6\xa0\x87\xe8\xa6\x81\xe6\xb1\x82", "application/octet-stream")},
        )
        assert first.status_code == 201
        first_document = first.json()
        assert first_document["mime_type"] == "text/plain"
        assert first_document["parse_status"] == "pending"
        assert first_document["index_status"] == "pending"
        assert first_document["version_number"] == 1
        assert first_document["supersedes_document_id"] is None

        replacement = client.post(
            "/documents/upload",
            params={"defer_ingest": True},
            data={
                "bundle_id": bundle_id,
                "supersedes_document_id": first_document["id"],
            },
            files={"file": ("RFP.txt", b"\xe6\x9b\xb4\xe6\x96\xb0\xe5\x90\x8e\xe7\x9a\x84\xe6\x8a\x95\xe6\xa0\x87\xe8\xa6\x81\xe6\xb1\x82", "text/plain")},
        )

    assert replacement.status_code == 201
    replacement_document = replacement.json()
    assert replacement_document["version_number"] == 2
    assert replacement_document["supersedes_document_id"] == first_document["id"]

    with patch(
        "app.adapters.storage.upload_bytes",
        side_effect=lambda _project_id, object_name, _data, _mime_type: f"{project_id}/{object_name}",
    ):
        duplicate_replacement = client.post(
            "/documents/upload",
            params={"defer_ingest": True},
            data={
                "bundle_id": bundle_id,
                "supersedes_document_id": first_document["id"],
            },
            files={"file": ("RFP.txt", b"duplicate replacement", "text/plain")},
        )

    assert duplicate_replacement.status_code == 409
    assert duplicate_replacement.json()["detail"] == "This document version already has a replacement"

    listed = client.get(f"/documents?bundle_id={bundle_id}")
    assert listed.status_code == 200
    assert [item["version_number"] for item in listed.json()["items"]] == [2, 1]


def test_upload_rejects_unsupported_types_before_storage(client) -> None:
    _project_id, bundle_id = _create_upload_bundle(client, "Document Type Contract")

    with patch("app.adapters.storage.upload_bytes") as upload_bytes:
        response = client.post(
            "/documents/upload",
            data={"bundle_id": bundle_id},
            files={"file": ("malware.exe", b"MZ...", "application/x-msdownload")},
        )

    assert response.status_code == 415
    assert upload_bytes.call_count == 0


def test_upload_archive_stores_file_without_queueing_text_ingestion(client) -> None:
    project_id, bundle_id = _create_upload_bundle(client, "Archive Storage Contract")

    with (
        patch(
            "app.adapters.storage.upload_bytes",
            side_effect=lambda _project_id, object_name, _data, _mime_type: f"{project_id}/{object_name}",
        ),
        patch("app.documents.service.celery.send_task") as send_task,
    ):
        response = client.post(
            "/documents/upload",
            params={"bundle_id": bundle_id},
            files={"file": ("投标软件.zip", b"PK\x03\x04archive", "application/octet-stream")},
        )

    assert response.status_code == 201
    document = response.json()
    assert document["mime_type"] == "application/zip"
    assert document["parse_status"] == "not_applicable"
    assert document["index_status"] == "not_applicable"
    assert document["ingest_queued"] is False
    send_task.assert_not_called()

    bundles = client.get(f"/bundles?project_id={project_id}")
    assert bundles.status_code == 200
    assert next(item for item in bundles.json() if item["id"] == bundle_id)["ingest_status"] == "ingested"

    reingest = client.post(f"/bundles/{bundle_id}/reingest")
    assert reingest.status_code == 409
    assert "可下载附件" in reingest.json()["detail"]


def test_replacement_document_must_stay_in_the_same_bundle(client) -> None:
    project_id, first_bundle_id = _create_upload_bundle(client, "Document Scope Contract")
    second_bundle = client.post(
        "/bundles",
        json={"project_id": project_id, "label": "另一个资料包", "source_type": "upload"},
    )
    assert second_bundle.status_code == 201

    with patch(
        "app.adapters.storage.upload_bytes",
        side_effect=lambda _project_id, object_name, _data, _mime_type: f"{project_id}/{object_name}",
    ):
        first = client.post(
            "/documents/upload",
            params={"defer_ingest": True},
            data={"bundle_id": first_bundle_id},
            files={"file": ("source.md", b"# \xe8\xb5\x84\xe6\x96\x99", "text/markdown")},
        )
        assert first.status_code == 201
        invalid_replacement = client.post(
            "/documents/upload",
            data={
                "bundle_id": second_bundle.json()["id"],
                "supersedes_document_id": first.json()["id"],
            },
            files={"file": ("source.md", b"# \xe6\x9b\xb4\xe6\x96\xb0", "text/markdown")},
        )

    assert invalid_replacement.status_code == 422
    assert invalid_replacement.json()["detail"] == "Replacement document must belong to the same bundle"


def test_upload_queues_ingestion_only_after_document_is_durable(client) -> None:
    project_id, bundle_id = _create_upload_bundle(client, "Document Dispatch Contract")

    with (
        patch(
            "app.adapters.storage.upload_bytes",
            side_effect=lambda _project_id, object_name, _data, _mime_type: f"{project_id}/{object_name}",
        ),
        patch("app.documents.service.celery.send_task") as send_task,
    ):
        deferred = client.post(
            "/documents/upload",
            params={"bundle_id": bundle_id, "defer_ingest": True},
            files={"file": ("part-one.txt", b"First upload", "text/plain")},
        )
        assert deferred.status_code == 201
        assert deferred.json()["ingest_queued"] is False
        send_task.assert_not_called()

        queued = client.post(
            "/documents/upload",
            params={"bundle_id": bundle_id},
            files={"file": ("part-two.txt", b"Second upload", "text/plain")},
        )

    assert queued.status_code == 201
    assert queued.json()["ingest_queued"] is True
    send_task.assert_called_once_with("worker.ingest_bundle", args=[bundle_id])
    bundles = client.get(f"/bundles?project_id={project_id}")
    assert bundles.status_code == 200
    assert next(item for item in bundles.json() if item["id"] == bundle_id)["ingest_status"] == "queued"


def test_multi_file_intake_defers_each_upload_then_queues_one_bundle_job(client) -> None:
    """A user-selected multi-file pack must not race its own background ingest."""
    project_id, bundle_id = _create_upload_bundle(client, "Multi File Intake Contract")

    with (
        patch(
            "app.adapters.storage.upload_bytes",
            side_effect=lambda _project_id, object_name, _data, _mime_type: f"{project_id}/{object_name}",
        ),
        patch("app.bundles.service.celery.send_task") as reingest_task,
    ):
        for filename, payload in (("rfp.txt", b"RFP requirements"), ("capability.txt", b"Capability evidence")):
            uploaded = client.post(
                "/documents/upload",
                params={"bundle_id": bundle_id, "defer_ingest": True},
                files={"file": (filename, payload, "text/plain")},
            )
            assert uploaded.status_code == 201
            assert uploaded.json()["ingest_queued"] is False

        queued = client.post(f"/bundles/{bundle_id}/reingest")

    assert queued.status_code == 200
    reingest_task.assert_called_once_with("worker.ingest_bundle", args=[bundle_id])
    listed = client.get(f"/documents?bundle_id={bundle_id}")
    assert listed.status_code == 200
    assert listed.json()["total"] == 2
