"""Bounded, provenance-preserving imports of public web sources.

Search providers discover candidate URLs.  This module imports one chosen
source into the document pipeline; it deliberately does not crawl a site or
follow links beyond the redirect chain for the requested URL.
"""

from __future__ import annotations

import hashlib
import ipaddress
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from time import monotonic
from typing import Literal
from urllib.parse import unquote, urljoin, urlparse

import httpx
from trafilatura import extract

from contracts.document_ingestion import MAX_STORED_ARTIFACT_BYTES, MAX_SOURCE_DOCUMENT_BYTES

from .import_errors import RemoteImportError


MAX_WEB_IMPORT_BYTES = MAX_SOURCE_DOCUMENT_BYTES
MAX_WEB_IMPORT_ARTIFACT_BYTES = MAX_STORED_ARTIFACT_BYTES
MAX_WEB_IMPORT_SECONDS = 25.0
MAX_WEB_IMPORT_ARTIFACT_SECONDS = 180.0
# Large public attachments are downloaded only by a background Worker. Keep a
# bounded but practical deadline for slow government document hosts; the byte
# ceiling is still the primary resource safeguard.
MAX_BACKGROUND_ARTIFACT_SECONDS = 15 * 60.0
MAX_WEB_IMPORT_REDIRECTS = 5

_HTML_TYPES = {"text/html", "application/xhtml+xml"}
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


@dataclass(frozen=True)
class DownloadedWebSource:
    """A normalized source ready for the ordinary source-document pipeline."""

    data: bytes
    content_type: str
    filename: str
    source_url: str


@dataclass(frozen=True)
class DownloadedRemoteArtifact:
    """One streamed remote artifact staged on the Worker filesystem."""

    file_path: Path
    byte_count: int
    checksum: str
    signature: bytes
    content_type: str
    filename: str
    source_url: str

    def cleanup(self) -> None:
        self.file_path.unlink(missing_ok=True)


@dataclass(frozen=True)
class RemoteDocumentCandidate:
    """A direct document link discovered on one public notice page."""

    url: str
    filename: str
    title: str
    content_type_hint: str | None = None


_DOCUMENT_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".rar",
    ".7z",
    ".txt",
    ".csv",
)
_DOCUMENT_LINK_TERMS = (
    "下载",
    "附件",
    "原件",
    "招标文件",
    "采购文件",
    "投标文件",
    "技术规范",
    "资格审查",
)
_NON_DOCUMENT_LINK_TERMS = ("公告正文", "公告详情", "正文", "详情", "查看全文", "首页")


def download_web_source(
    url: str,
    *,
    filename: str | None = None,
    import_mode: Literal["artifact", "web_evidence"] = "artifact",
) -> DownloadedWebSource:
    """Download one public HTTP(S) resource with bounded redirects and bytes.

    The caller owns authorization and durable storage.  Keeping the network
    read here makes the same guardrails reusable by an Agent capability and a
    future user-facing research-import flow.
    """

    if import_mode not in {"artifact", "web_evidence"}:
        raise ValueError("import_mode must be artifact or web_evidence")
    response_data, response_content_type, final_url = _fetch_remote_resource(
        url,
        max_bytes=MAX_WEB_IMPORT_ARTIFACT_BYTES if import_mode == "artifact" else MAX_WEB_IMPORT_BYTES,
        max_seconds=(
            MAX_WEB_IMPORT_ARTIFACT_SECONDS
            if import_mode == "artifact"
            else MAX_WEB_IMPORT_SECONDS
        ),
    )
    if import_mode == "artifact" and _looks_like_html(response_data, response_content_type):
        raise RemoteImportError(
            "remote_not_artifact",
            "该地址返回的是网页而不是可下载附件。请提供 PDF、DOCX、XLSX 或压缩包的直接地址；"
            "如需保存公告正文，请明确选择“保存网页正文”。",
            retryable=False,
        )

    return _normalize_download(
        data=response_data,
        content_type=response_content_type,
        source_url=final_url,
        filename=filename,
        import_mode=import_mode,
    )


def download_remote_artifact_to_tempfile(
    url: str,
    *,
    filename: str | None = None,
) -> DownloadedRemoteArtifact:
    """Stream one confirmed public attachment to a temporary Worker file.

    This path is intentionally artifact-only. It keeps a slow ZIP/PDF out of
    the Agent request and avoids retaining up to the configured attachment
    limit in one Worker process. Callers must always invoke ``cleanup`` after
    MinIO storage has completed or failed.
    """

    current_url = _require_public_http_url(url)
    started_at = monotonic()
    temp = NamedTemporaryFile(prefix="bidpilot-remote-", suffix=".download", delete=False)
    temp_path = Path(temp.name)
    final_url = current_url
    response_content_type = ""
    response_filename: str | None = None
    signature = bytearray()
    checksum = hashlib.sha256()
    total = 0
    completed = False

    try:
        with temp:
            with httpx.Client(
                timeout=httpx.Timeout(connect=5.0, read=30.0, write=8.0, pool=5.0),
                follow_redirects=False,
                headers={"User-Agent": "BidPilotSourceImport/1.0"},
                trust_env=False,
            ) as client:
                for _ in range(MAX_WEB_IMPORT_REDIRECTS + 1):
                    _ensure_within_deadline(started_at, max_seconds=MAX_BACKGROUND_ARTIFACT_SECONDS)
                    with client.stream("GET", current_url) as response:
                        if response.status_code in _REDIRECT_STATUSES:
                            location = response.headers.get("location")
                            if not location:
                                raise RemoteImportError(
                                    "remote_redirect_invalid",
                                    "远程站点返回了无效跳转，未下载任何资料。",
                                    retryable=False,
                                )
                            current_url = _require_public_http_url(urljoin(current_url, location))
                            continue
                        if response.status_code >= 400:
                            raise _http_status_error(response.status_code)
                        if response.status_code < 200 or response.status_code >= 300:
                            raise RemoteImportError(
                                "remote_source_unavailable",
                                "远程资料站点返回了无法下载的响应，请稍后再试或改用本地上传。",
                                retryable=True,
                            )
                        declared_size = response.headers.get("content-length")
                        if declared_size and declared_size.isdigit() and int(declared_size) > MAX_WEB_IMPORT_ARTIFACT_BYTES:
                            raise RemoteImportError(
                                "remote_too_large",
                                _too_large_message(MAX_WEB_IMPORT_ARTIFACT_BYTES),
                                retryable=False,
                            )
                        for chunk in response.iter_bytes():
                            _ensure_within_deadline(started_at, max_seconds=MAX_BACKGROUND_ARTIFACT_SECONDS)
                            total += len(chunk)
                            if total > MAX_WEB_IMPORT_ARTIFACT_BYTES:
                                raise RemoteImportError(
                                    "remote_too_large",
                                    _too_large_message(MAX_WEB_IMPORT_ARTIFACT_BYTES),
                                    retryable=False,
                                )
                            if len(signature) < 512:
                                signature.extend(chunk[: 512 - len(signature)])
                            checksum.update(chunk)
                            temp.write(chunk)
                        response_content_type = _normalized_content_type(response.headers.get("content-type"))
                        response_filename = _filename_from_content_disposition(response.headers.get("content-disposition"))
                        final_url = str(response.url)
                        completed = True
                        break
                else:
                    raise RemoteImportError(
                        "remote_redirect_limit",
                        "远程地址跳转次数过多，未下载任何资料。请提供最终附件直链。",
                        retryable=False,
                    )

        if not completed or total == 0:
            raise RemoteImportError(
                "remote_empty_response",
                "远程站点没有返回可保存的文件。请确认附件地址后再试。",
                retryable=True,
            )
        prefix = bytes(signature)
        if _looks_like_html(prefix, response_content_type):
            raise RemoteImportError(
                "remote_not_artifact",
                "该地址返回的是网页而不是可下载附件。请提供 PDF、DOCX、XLSX 或压缩包的直接地址；"
                "如需保存公告正文，请明确选择“保存网页正文”。",
                retryable=False,
            )
        candidate_filename = filename or response_filename
        resolved_filename = (
            _safe_filename(candidate_filename)
            if candidate_filename
            else _filename_from_url(final_url)
        )
        return DownloadedRemoteArtifact(
            file_path=temp_path,
            byte_count=total,
            checksum=checksum.hexdigest(),
            signature=prefix,
            content_type=response_content_type or "application/octet-stream",
            filename=resolved_filename,
            source_url=final_url,
        )
    except httpx.TimeoutException as exc:
        raise RemoteImportError(
            "remote_timeout",
            f"远程站点在 {int(MAX_BACKGROUND_ARTIFACT_SECONDS // 60)} 分钟内未完成附件下载。请稍后重试，或先手动下载后上传。",
            retryable=True,
        ) from exc
    except httpx.ConnectError as exc:
        detail = str(exc).casefold()
        if "wrong version number" in detail or "ssl" in detail or "tls" in detail:
            raise RemoteImportError(
                "remote_protocol_error",
                "远程站点的连接协议不兼容。请使用公告页给出的原始附件地址，或先手动下载后上传。",
                retryable=False,
            ) from exc
        raise RemoteImportError(
            "remote_connection_failed",
            "无法连接到远程资料站点。请稍后重试，或先手动下载后上传。",
            retryable=True,
        ) from exc
    except httpx.HTTPError as exc:
        raise RemoteImportError(
            "remote_connection_failed",
            "无法下载远程资料。请确认它是公开可访问的附件直链，或先手动下载后上传。",
            retryable=True,
        ) from exc
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def fetch_public_http_resource(url: str) -> tuple[bytes, str, str]:
    """Fetch one bounded public HTTP(S) resource without importing it.

    Feed adapters use this narrow primitive to normalize public RSS and JSON
    sources. It intentionally inherits the same SSRF, redirect, byte-size and
    timeout controls used by user-triggered remote document imports.
    """

    return _fetch_remote_resource(url)


def validate_public_http_url(url: str) -> str:
    """Validate an outbound public HTTP(S) address without issuing a request.

    Webhook delivery uses the same literal-host restrictions as document and
    feed imports. Redirects are deliberately disabled for webhook POSTs so a
    validated public endpoint cannot bounce the worker into a private target.
    """

    return _require_public_http_url(url)


def discover_remote_documents(url: str, *, max_results: int = 10) -> list[RemoteDocumentCandidate]:
    """Discover direct document links without persisting or downloading them.

    This intentionally reads one public HTML page only. It does not crawl
    linked pages, follow attachment links, or put the page into a project.
    """

    limit = max(1, min(int(max_results), 20))
    data, content_type, final_url = _fetch_remote_resource(
        url,
        max_bytes=MAX_WEB_IMPORT_BYTES,
        max_seconds=MAX_WEB_IMPORT_SECONDS,
    )
    if not _looks_like_html(data, content_type):
        return []

    parser = _DocumentLinkParser()
    parser.feed(data.decode("utf-8", errors="replace"))
    parser.close()
    candidates: list[RemoteDocumentCandidate] = []
    seen: set[str] = set()
    for href, title in parser.links:
        if len(candidates) >= limit:
            break
        try:
            candidate_url = _require_public_http_url(urljoin(final_url, href))
        except ValueError:
            continue
        filename = _filename_from_url(candidate_url)
        label = " ".join((title, filename)).strip()
        if not _is_document_link(candidate_url, label):
            continue
        if candidate_url in seen:
            continue
        seen.add(candidate_url)
        candidates.append(
            RemoteDocumentCandidate(
                url=candidate_url,
                filename=filename,
                title=title or filename,
                content_type_hint=_content_type_hint(filename),
            )
        )
    return candidates


class _DocumentLinkParser(HTMLParser):
    """Collect anchor href/text pairs using the stdlib HTML parser."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a" or self._href is not None:
            return
        href = dict(attrs).get("href")
        if isinstance(href, str) and href.strip():
            self._href = href.strip()
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._href is None:
            return
        title = re.sub(r"\s+", " ", " ".join(self._text)).strip()[:200]
        self.links.append((self._href, title))
        self._href = None
        self._text = []


def _fetch_remote_resource(
    url: str,
    *,
    max_bytes: int = MAX_WEB_IMPORT_BYTES,
    max_seconds: float = MAX_WEB_IMPORT_SECONDS,
) -> tuple[bytes, str, str]:
    current_url = _require_public_http_url(url)
    started_at = monotonic()
    response_data: bytes | None = None
    response_content_type = ""
    final_url = current_url

    try:
        with httpx.Client(
            timeout=httpx.Timeout(connect=5.0, read=8.0, write=8.0, pool=5.0),
            follow_redirects=False,
            headers={"User-Agent": "BidPilotSourceImport/1.0"},
            trust_env=False,
        ) as client:
            for _ in range(MAX_WEB_IMPORT_REDIRECTS + 1):
                _ensure_within_deadline(started_at, max_seconds=max_seconds)
                with client.stream("GET", current_url) as response:
                    if response.status_code in _REDIRECT_STATUSES:
                        location = response.headers.get("location")
                        if not location:
                            raise RemoteImportError(
                                "remote_redirect_invalid",
                                "远程站点返回了无效跳转，未下载任何资料。",
                                retryable=False,
                            )
                        current_url = _require_public_http_url(urljoin(current_url, location))
                        continue
                    if response.status_code >= 400:
                        raise _http_status_error(response.status_code)
                    if response.status_code < 200 or response.status_code >= 300:
                        raise RemoteImportError(
                            "remote_source_unavailable",
                            "远程资料站点返回了无法下载的响应，请稍后再试或改用本地上传。",
                            retryable=True,
                        )

                    declared_size = response.headers.get("content-length")
                    if declared_size and declared_size.isdigit() and int(declared_size) > max_bytes:
                        raise RemoteImportError(
                            "remote_too_large",
                            _too_large_message(max_bytes),
                            retryable=False,
                        )

                    chunks: list[bytes] = []
                    total = 0
                    for chunk in response.iter_bytes():
                        _ensure_within_deadline(started_at, max_seconds=max_seconds)
                        total += len(chunk)
                        if total > max_bytes:
                            raise RemoteImportError(
                                "remote_too_large",
                                _too_large_message(max_bytes),
                                retryable=False,
                            )
                        chunks.append(chunk)
                    response_data = b"".join(chunks)
                    response_content_type = _normalized_content_type(response.headers.get("content-type"))
                    final_url = str(response.url)
                    break
            else:
                raise RemoteImportError(
                    "remote_redirect_limit",
                    "远程地址跳转次数过多，未下载任何资料。请提供最终附件直链。",
                    retryable=False,
                )
    except httpx.TimeoutException as exc:
        raise RemoteImportError(
            "remote_timeout",
            "远程站点在 25 秒内没有返回文件。请稍后重试，或先手动下载后上传。",
            retryable=True,
        ) from exc
    except httpx.ConnectError as exc:
        detail = str(exc).casefold()
        if "wrong version number" in detail or "ssl" in detail or "tls" in detail:
            raise RemoteImportError(
                "remote_protocol_error",
                "远程站点的连接协议不兼容。请使用公告页给出的原始附件地址，或先手动下载后上传。",
                retryable=False,
            ) from exc
        raise RemoteImportError(
            "remote_connection_failed",
            "无法连接到远程资料站点。请稍后重试，或先手动下载后上传。",
            retryable=True,
        ) from exc
    except httpx.HTTPError as exc:
        raise RemoteImportError(
            "remote_connection_failed",
            "无法下载远程资料。请确认它是公开可访问的附件直链，或先手动下载后上传。",
            retryable=True,
        ) from exc

    if response_data is None:
        raise RemoteImportError(
            "remote_empty_response",
            "远程站点没有返回可保存的文件。请确认附件地址后再试。",
            retryable=True,
        )
    return response_data, response_content_type, final_url


def _normalize_download(
    *,
    data: bytes,
    content_type: str,
    source_url: str,
    filename: str | None,
    import_mode: Literal["artifact", "web_evidence"] = "artifact",
) -> DownloadedWebSource:
    resolved_filename = _safe_filename(filename) if filename else _filename_from_url(source_url)
    if import_mode == "web_evidence" and _looks_like_html(data, content_type):
        markdown = extract(
            data.decode("utf-8", errors="replace"),
            output_format="markdown",
            include_comments=False,
            include_tables=True,
            include_links=True,
            url=source_url,
        )
        if not markdown or not markdown.strip():
            raise ValueError("The webpage did not contain extractable article text")
        if not resolved_filename.lower().endswith((".md", ".markdown")):
            resolved_filename = f"{PurePosixPath(resolved_filename).stem or 'web-source'}.md"
        return DownloadedWebSource(
            data=markdown.encode("utf-8"),
            content_type="text/markdown",
            filename=resolved_filename,
            source_url=source_url,
        )
    return DownloadedWebSource(
        data=data,
        content_type=content_type or "application/octet-stream",
        filename=resolved_filename,
        source_url=source_url,
    )


def _looks_like_html(data: bytes, content_type: str) -> bool:
    if content_type in _HTML_TYPES:
        return True
    sample = data[:512].lstrip().lower()
    return sample.startswith((b"<!doctype html", b"<html", b"<head", b"<body"))


def _is_document_link(url: str, label: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.casefold()
    if path.endswith(_DOCUMENT_EXTENSIONS):
        return True
    lowered = f"{label} {parsed.query}".casefold()
    if any(term in lowered for term in _NON_DOCUMENT_LINK_TERMS) and not any(
        term in lowered for term in ("下载", "附件", "download", "attachment")
    ):
        return False
    return any(term in lowered for term in _DOCUMENT_LINK_TERMS)


def _content_type_hint(filename: str) -> str | None:
    suffix = PurePosixPath(filename).suffix.casefold()
    return {
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".ppt": "application/vnd.ms-powerpoint",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".zip": "application/zip",
        ".rar": "application/vnd.rar",
        ".7z": "application/x-7z-compressed",
        ".txt": "text/plain",
        ".csv": "text/csv",
    }.get(suffix)


def _require_public_http_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must be a public HTTP(S) address")
    _ensure_public_host(parsed.hostname)
    return parsed.geturl()


def _ensure_public_host(hostname: str) -> None:
    normalized = hostname.lower().rstrip(".")
    if normalized == "localhost" or normalized.endswith((".local", ".internal")):
        raise ValueError("Local or private network URLs cannot be imported")
    # Docker Desktop's controlled egress can resolve every public hostname to
    # an internal proxy address. Reject literal private IPs here and let the
    # container network policy govern hostname resolution, otherwise that proxy
    # would make all public URLs look like SSRF targets.
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return
    if not address.is_global:
        raise ValueError("Local or private network URLs cannot be imported")


def _ensure_within_deadline(started_at: float, *, max_seconds: float = MAX_WEB_IMPORT_SECONDS) -> None:
    if monotonic() - started_at > max_seconds:
        raise RemoteImportError(
            "remote_timeout",
            f"远程站点在 {int(max_seconds)} 秒内没有返回文件。请稍后重试，或先手动下载后上传。",
            retryable=True,
        )


def _too_large_message(max_bytes: int) -> str:
    limit_mb = max(1, max_bytes // (1024 * 1024))
    return (
        f"远程文件超过当前 {limit_mb} MB 的安全导入上限。"
        "请先下载后通过资料中心上传，或选择更小的附件。"
    )


def _http_status_error(status_code: int) -> RemoteImportError:
    if status_code in {401, 403}:
        return RemoteImportError(
            "remote_access_denied",
            "远程站点拒绝下载，附件可能要求登录、Cookie 或访问白名单。BidPilot 不会绕过访问控制；请先手动下载后上传。",
            retryable=False,
        )
    if status_code == 404:
        return RemoteImportError(
            "remote_not_found",
            "未找到该远程附件。请回到公告页确认最新附件直链。",
            retryable=False,
        )
    if status_code == 429:
        return RemoteImportError(
            "remote_rate_limited",
            "远程站点暂时限制了下载，请稍后重试，避免反复请求。",
            retryable=True,
        )
    if status_code >= 500:
        return RemoteImportError(
            "remote_source_unavailable",
            "远程资料站点暂时不可用，请稍后重试或先手动下载后上传。",
            retryable=True,
        )
    return RemoteImportError(
        "remote_source_unavailable",
        "远程资料站点拒绝了这次下载，请确认附件直链后再试。",
        retryable=False,
    )


def _normalized_content_type(value: str | None) -> str:
    return (value or "").split(";", 1)[0].strip().lower()


def _filename_from_url(url: str) -> str:
    name = unquote(PurePosixPath(urlparse(url).path).name).strip()
    return _safe_filename(name or "web-source")


def _filename_from_content_disposition(value: str | None) -> str | None:
    """Extract an RFC 5987/legacy attachment name without trusting a path."""
    if not value:
        return None
    extended = re.search(r"filename\*\s*=\s*[^']*''([^;]+)", value, flags=re.IGNORECASE)
    if extended:
        return _safe_filename(unquote(extended.group(1).strip().strip('"')))
    legacy = re.search(r"filename\s*=\s*(?:\"([^\"]+)\"|([^;]+))", value, flags=re.IGNORECASE)
    if not legacy:
        return None
    return _safe_filename((legacy.group(1) or legacy.group(2) or "").strip())


def _safe_filename(value: str) -> str:
    name = value.replace("\\", "/").rsplit("/", 1)[-1].strip()
    name = re.sub(r'[<>:"/\\\\|?*\x00-\x1f]', "-", name)
    return name[:200] or "web-source"
