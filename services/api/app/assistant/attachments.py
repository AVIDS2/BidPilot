"""Assistant attachment extraction helpers."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from time import time
from uuid import uuid4

from .schemas import (
    AssistantAttachmentKind,
    AssistantAttachmentPayload,
    AssistantAttachmentUploadResponse,
)

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENT_TEXT_CHARS = 16_000
MAX_TOTAL_ATTACHMENT_TEXT_CHARS = 24_000
ATTACHMENT_CACHE_TTL_SECONDS = 60 * 60

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".xml",
    ".html",
    ".htm",
    ".log",
}

_ATTACHMENT_TEXT_CACHE: dict[str, tuple[float, str]] = {}


def extract_attachment_text(
    *,
    filename: str,
    content_type: str,
    data: bytes,
    kind: AssistantAttachmentKind | None = None,
) -> AssistantAttachmentUploadResponse:
    """Extract readable text for a chat-scoped assistant attachment."""
    safe_name = filename or "untitled"
    mime_type = content_type or "application/octet-stream"
    attachment_kind: AssistantAttachmentKind = kind or ("image" if mime_type.startswith("image/") else "file")

    if attachment_kind == "image" or mime_type.startswith("image/"):
        return _response(
            name=safe_name,
            kind="image",
            mime_type=mime_type,
            size=len(data),
            status="unsupported",
            text="",
            error="当前不能读取图片像素或 OCR；请补充图片内容描述，或等待视觉模型接入。",
        )

    text = ""
    error: str | None = None
    try:
        if _is_docx(safe_name, mime_type):
            text = _extract_docx(data)
        elif _is_pdf(safe_name, mime_type):
            text = _extract_pdf(data)
            if not text:
                error = "PDF 文本提取失败或文件不可选择文本。"
        elif _is_plain_text(safe_name, mime_type):
            text = _decode_text(data)
        else:
            return _response(
                name=safe_name,
                kind=attachment_kind,
                mime_type=mime_type,
                size=len(data),
                status="unsupported",
                text="",
                error="暂不支持解析该附件格式。",
            )
    except Exception as exc:  # Defensive: never let a bad attachment break chat.
        return _response(
            name=safe_name,
            kind=attachment_kind,
            mime_type=mime_type,
            size=len(data),
            status="failed",
            text="",
            error=str(exc),
        )

    text = _normalize_text(text)
    if not text:
        return _response(
            name=safe_name,
            kind=attachment_kind,
            mime_type=mime_type,
            size=len(data),
            status="empty",
            text="",
            error=error,
        )

    return _response(
        name=safe_name,
        kind=attachment_kind,
        mime_type=mime_type,
        size=len(data),
        status="extracted",
        text=_truncate(text, MAX_ATTACHMENT_TEXT_CHARS),
        error=error,
    )


def build_attachment_context(message: str, attachments: list[AssistantAttachmentPayload]) -> str:
    """Append internal attachment context for the model without showing it in chat UI."""
    if not attachments:
        return message

    remaining = MAX_TOTAL_ATTACHMENT_TEXT_CHARS
    sections = [
        "【系统附件上下文】",
        "以下内容来自用户本轮上传的附件。优先结合可读附件正文回答；不要声称读取了未提供正文的图片、截图或不支持文件。",
    ]

    for index, attachment in enumerate(attachments, start=1):
        name = attachment.name
        mime_type = attachment.mime_type or "unknown"
        size = attachment.size if attachment.size is not None else 0
        header = f"附件 {index}: {name} ({attachment.kind}, {mime_type}, {size} bytes)"
        text = (attachment.extracted_text or _resolve_cached_attachment_text(attachment.id)).strip()

        if text and remaining > 0:
            clipped = _truncate(text, min(MAX_ATTACHMENT_TEXT_CHARS, remaining))
            remaining -= len(clipped)
            sections.append(f"{header}\n可读正文：\n{clipped}")
            continue

        if attachment.kind == "image":
            sections.append(
                f"{header}\n说明：当前不能读取图片像素或 OCR；只能使用文件名、MIME 类型和用户额外描述。"
            )
            continue

        reason = attachment.error or _status_reason(attachment.extraction_status)
        sections.append(f"{header}\n说明：未获得可读正文。{reason}")

    return "\n\n".join([message, "\n\n".join(sections)]).strip()


def remember_attachment_text(extraction: AssistantAttachmentUploadResponse) -> None:
    """Keep extracted text server-side for the next assistant turn."""
    text = extraction.extracted_text.strip()
    if not text:
        return
    _purge_expired_attachment_text()
    _ATTACHMENT_TEXT_CACHE[extraction.id] = (time(), text)


def _response(
    *,
    name: str,
    kind: AssistantAttachmentKind,
    mime_type: str,
    size: int,
    status: str,
    text: str,
    error: str | None = None,
) -> AssistantAttachmentUploadResponse:
    return AssistantAttachmentUploadResponse(
        id=f"att_{uuid4().hex}",
        name=name,
        kind=kind,
        mime_type=mime_type,
        size=size,
        extraction_status=status,  # type: ignore[arg-type]
        extracted_text=text,
        error=error,
    )


def _resolve_cached_attachment_text(attachment_id: str | None) -> str:
    if not attachment_id:
        return ""
    _purge_expired_attachment_text()
    cached = _ATTACHMENT_TEXT_CACHE.get(attachment_id)
    return cached[1] if cached else ""


def _purge_expired_attachment_text() -> None:
    now = time()
    expired = [
        attachment_id
        for attachment_id, (created_at, _text) in _ATTACHMENT_TEXT_CACHE.items()
        if now - created_at > ATTACHMENT_CACHE_TTL_SECONDS
    ]
    for attachment_id in expired:
        _ATTACHMENT_TEXT_CACHE.pop(attachment_id, None)


def _is_docx(filename: str, mime_type: str) -> bool:
    return Path(filename).suffix.lower() == ".docx" or mime_type == _DOCX_MIME


def _is_pdf(filename: str, mime_type: str) -> bool:
    return Path(filename).suffix.lower() == ".pdf" or mime_type == "application/pdf"


def _is_plain_text(filename: str, mime_type: str) -> bool:
    return mime_type.startswith("text/") or Path(filename).suffix.lower() in _TEXT_EXTENSIONS


def _extract_docx(data: bytes) -> str:
    from docx import Document

    document = Document(BytesIO(data))
    parts: list[str] = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n\n".join(parts)


def _extract_pdf(data: bytes) -> str:
    try:
        import pymupdf  # type: ignore[import-not-found]
    except Exception:
        return ""

    doc = pymupdf.open(stream=data, filetype="pdf")
    try:
        return "\n\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _normalize_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip()


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars].rstrip()}\n\n[附件正文已截断]"


def _status_reason(status: str | None) -> str:
    if status == "empty":
        return "文件没有提取到文本。"
    if status == "failed":
        return "解析失败。"
    if status == "unsupported":
        return "格式暂不支持。"
    return "附件没有提供提取文本。"
