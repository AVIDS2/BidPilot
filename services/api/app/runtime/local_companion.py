"""Narrow local artifact companion primitives.

This code is meant to run on a user's own machine, never inside the API or
worker container.  It deliberately supports a single operation: stream a
confirmed HTTP(S) artifact into a user-selected directory.  It is not a shell
or a remote-command transport.
"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


MAX_LOCAL_ARTIFACT_BYTES = 512 * 1024 * 1024
_SAFE_FILENAME = re.compile(r"^[^<>:\\|?*/\x00-\x1f]{1,180}$")
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")


class LocalCompanionError(RuntimeError):
    """A public, user-actionable failure from the local downloader."""


class LocalArtifactRequest(BaseModel):
    """A confirmed artifact request that a local companion may perform."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_id: str = Field(min_length=1, max_length=120)
    url: HttpUrl
    filename: str = Field(min_length=1, max_length=180)
    max_bytes: int = Field(default=MAX_LOCAL_ARTIFACT_BYTES, ge=1, le=MAX_LOCAL_ARTIFACT_BYTES)

    @field_validator("filename")
    @classmethod
    def _validate_filename(cls, value: str) -> str:
        if value in {".", ".."} or not _SAFE_FILENAME.fullmatch(value):
            raise ValueError("filename must be a plain local filename")
        return value

    @field_validator("request_id")
    @classmethod
    def _validate_request_id(cls, value: str) -> str:
        if not _SAFE_REQUEST_ID.fullmatch(value):
            raise ValueError("request_id must be a safe identifier")
        return value


class LocalArtifactReceipt(BaseModel):
    """Non-sensitive completion data suitable for displaying or uploading."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str
    filename: str
    byte_count: int
    sha256: str
    completed_at: datetime


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        del request, fp, code, msg, headers, newurl
        raise LocalCompanionError("下载地址发生重定向，请在确认后使用最终公开直链重新发起下载。")


def download_local_artifact(
    request: LocalArtifactRequest,
    *,
    destination_directory: Path,
    allowed_hosts: Iterable[str] = (),
    timeout_seconds: float = 30.0,
) -> LocalArtifactReceipt:
    """Stream a confirmed artifact to a user-owned directory atomically.

    Redirects are rejected rather than silently following an unreviewed host.
    ``allowed_hosts`` is an optional exact-or-subdomain allow-list managed by
    the local user.  The destination path itself never leaves this process.
    """
    parsed = urlparse(str(request.url))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise LocalCompanionError("仅支持带主机名的 HTTP(S) 下载地址。")
    _validate_host(parsed.hostname, allowed_hosts)
    target_directory = destination_directory.expanduser().resolve()
    target_directory.mkdir(parents=True, exist_ok=True)
    target = (target_directory / request.filename).resolve()
    if target.parent != target_directory:
        raise LocalCompanionError("目标文件必须位于指定下载目录内。")
    temporary = target.with_name(f".{target.name}.{request.request_id}.part")
    try:
        opener = build_opener(_NoRedirectHandler())
        response = opener.open(
            Request(str(request.url), headers={"User-Agent": "BidPilot-Local-Companion/0.1"}),
            timeout=timeout_seconds,
        )
        with response, temporary.open("xb") as output:
            content_type = str(response.headers.get("Content-Type") or "").casefold()
            if content_type.startswith("text/html"):
                raise LocalCompanionError("远程地址返回了网页而非资料文件，请确认最终附件直链。")
            declared_size = response.headers.get("Content-Length")
            if declared_size and declared_size.isdigit() and int(declared_size) > request.max_bytes:
                raise LocalCompanionError("远程文件超过本次允许的大小上限。")
            digest = hashlib.sha256()
            total = 0
            while chunk := response.read(256 * 1024):
                total += len(chunk)
                if total > request.max_bytes:
                    raise LocalCompanionError("远程文件超过本次允许的大小上限。")
                digest.update(chunk)
                output.write(chunk)
        os.replace(temporary, target)
    except LocalCompanionError:
        _remove_if_exists(temporary)
        raise
    except HTTPError as exc:
        _remove_if_exists(temporary)
        raise LocalCompanionError(f"远程服务器返回 HTTP {exc.code}，未保存文件。") from exc
    except (OSError, URLError) as exc:
        _remove_if_exists(temporary)
        raise LocalCompanionError("本地下载失败，未保存不完整文件。") from exc

    return LocalArtifactReceipt(
        request_id=request.request_id,
        filename=target.name,
        byte_count=total,
        sha256=digest.hexdigest(),
        completed_at=datetime.now(UTC),
    )


def _validate_host(host: str, allowed_hosts: Iterable[str]) -> None:
    hosts = tuple(item.casefold().strip(".") for item in allowed_hosts if item.strip())
    if not hosts:
        return
    normalized = host.casefold().strip(".")
    if any(normalized == item or normalized.endswith(f".{item}") for item in hosts):
        return
    raise LocalCompanionError("该下载主机不在本机允许列表中。")


def _remove_if_exists(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


__all__ = [
    "LocalArtifactReceipt",
    "LocalArtifactRequest",
    "LocalCompanionError",
    "MAX_LOCAL_ARTIFACT_BYTES",
    "download_local_artifact",
]
