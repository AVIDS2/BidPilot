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
            params={"bundle_id": bundle_id},
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
