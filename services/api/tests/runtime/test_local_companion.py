"""Local companion safety and artifact receipt contracts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.error import HTTPError

import pytest

from app.runtime.local_companion import (
    LocalArtifactRequest,
    LocalCompanionError,
    download_local_artifact,
)
from app.runtime.local_companion_cli import main


class _Response:
    def __init__(self, chunks: list[bytes], *, content_type: str = "application/pdf") -> None:
        self._chunks = iter(chunks)
        self.headers = {"Content-Type": content_type, "Content-Length": str(sum(map(len, chunks)))}

    def read(self, _size: int) -> bytes:
        return next(self._chunks, b"")

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None


def _request(**changes: object) -> LocalArtifactRequest:
    return LocalArtifactRequest.model_validate(
        {"request_id": "request-1", "url": "https://files.example.test/notice.pdf", "filename": "notice.pdf", **changes}
    )


def test_download_streams_atomically_and_returns_a_checksum(monkeypatch, tmp_path: Path) -> None:
    from app.runtime import local_companion as module

    body = b"a tender document"
    monkeypatch.setattr(module, "build_opener", lambda *_handlers: type("Opener", (), {"open": lambda *_args, **_kwargs: _Response([body])})())

    receipt = download_local_artifact(
        _request(),
        destination_directory=tmp_path,
        allowed_hosts=["example.test"],
    )

    assert (tmp_path / "notice.pdf").read_bytes() == body
    assert receipt.byte_count == len(body)
    assert receipt.sha256 == hashlib.sha256(body).hexdigest()
    assert not list(tmp_path.glob("*.part"))


def test_download_rejects_unapproved_host_before_network_access(tmp_path: Path) -> None:
    with pytest.raises(LocalCompanionError, match="允许列表"):
        download_local_artifact(_request(), destination_directory=tmp_path, allowed_hosts=["gov.example"])


@pytest.mark.parametrize("request_id", ["../outside", "request/child", "request\\child"])
def test_request_id_cannot_escape_the_temporary_file_path(request_id: str) -> None:
    with pytest.raises(ValueError, match="safe identifier"):
        _request(request_id=request_id)


def test_download_rejects_html_and_cleans_the_partial_file(monkeypatch, tmp_path: Path) -> None:
    from app.runtime import local_companion as module

    monkeypatch.setattr(
        module,
        "build_opener",
        lambda *_handlers: type("Opener", (), {"open": lambda *_args, **_kwargs: _Response([b"<html>"], content_type="text/html")})(),
    )

    with pytest.raises(LocalCompanionError, match="网页"):
        download_local_artifact(_request(), destination_directory=tmp_path)
    assert not list(tmp_path.iterdir())


def test_download_maps_http_errors_without_persisting_a_partial_file(monkeypatch, tmp_path: Path) -> None:
    from app.runtime import local_companion as module

    def fail(*_args, **_kwargs):
        raise HTTPError("https://files.example.test/notice.pdf", 403, "forbidden", {}, None)

    monkeypatch.setattr(module, "build_opener", lambda *_handlers: type("Opener", (), {"open": fail})())

    with pytest.raises(LocalCompanionError, match="HTTP 403"):
        download_local_artifact(_request(), destination_directory=tmp_path)
    assert not list(tmp_path.iterdir())


def test_cli_emits_only_a_non_sensitive_receipt(monkeypatch, tmp_path: Path, capsys) -> None:
    from app.runtime import local_companion_cli as module

    receipt = {
        "request_id": "request-1",
        "filename": "notice.pdf",
        "byte_count": 12,
        "sha256": "a" * 64,
        "completed_at": "2026-08-14T00:00:00Z",
    }

    class _Receipt:
        def model_dump_json(self) -> str:
            import json

            return json.dumps(receipt)

    captured: dict[str, object] = {}

    def _download(request, *, destination_directory, allowed_hosts):
        captured["request"] = request
        captured["directory"] = destination_directory
        captured["hosts"] = allowed_hosts
        return _Receipt()

    monkeypatch.setattr(module, "download_local_artifact", _download)

    assert main(
        [
            "download",
            "--request-id",
            "request-1",
            "--url",
            "https://files.example.test/notice.pdf",
            "--filename",
            "notice.pdf",
            "--directory",
            str(tmp_path),
            "--allow-host",
            "example.test",
        ]
    ) == 0

    assert captured["directory"] == tmp_path
    assert captured["hosts"] == ["example.test"]
    assert "https://files.example.test/notice.pdf" not in capsys.readouterr().out
