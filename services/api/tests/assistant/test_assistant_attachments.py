"""Tests for assistant attachment extraction and prompt context."""

from __future__ import annotations

from io import BytesIO

from docx import Document

from app.assistant.attachments import build_attachment_context, extract_attachment_text, remember_attachment_text
from app.assistant.schemas import AssistantAttachmentPayload


def _docx_bytes(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_extracts_docx_text_for_assistant_context() -> None:
    result = extract_attachment_text(
        filename="实践日志.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        data=_docx_bytes("投标项目进度：已完成 Hadoop 集群搭建。"),
    )

    assert result.extraction_status == "extracted"
    assert "Hadoop 集群搭建" in result.extracted_text


def test_attachment_context_resolves_server_side_cached_text() -> None:
    result = extract_attachment_text(
        filename="实践日志.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        data=_docx_bytes("投标项目进度：资料清单已经补齐。"),
    )
    remember_attachment_text(result)

    context = build_attachment_context(
        "请总结附件",
        [
            AssistantAttachmentPayload(
                id=result.id,
                name=result.name,
                kind=result.kind,
                mime_type=result.mime_type,
                size=result.size,
                extraction_status=result.extraction_status,
            )
        ],
    )

    assert "资料清单已经补齐" in context


def test_image_attachment_context_is_honest_about_unread_pixels() -> None:
    context = build_attachment_context(
        "看看这两个附件",
        [
            AssistantAttachmentPayload(
                id="att-image",
                name="screenshot.png",
                kind="image",
                mime_type="image/png",
                size=128,
                extraction_status="unsupported",
                extracted_text="",
            )
        ],
    )

    assert "screenshot.png" in context
    assert "当前不能读取图片像素或 OCR" in context
    assert "我看到了图片内容" not in context
