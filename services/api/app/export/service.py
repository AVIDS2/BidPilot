from __future__ import annotations

import hashlib
import html
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.access.service import require_deliverable_capability
from app.adapters.storage import download_storage_key, upload_bytes
from app.audit.service import record_audit_event
from app.auth.schemas import CurrentUser
from app.models import Deliverable, DeliverableExport, DeliverableSection, SectionVersion

from .schemas import (
    ApprovedSectionSnapshotRead,
    DeliverableExportRead,
)


SUPPORTED_EXPORT_FORMATS = frozenset({"docx", "pdf"})
MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


@dataclass(frozen=True)
class DeliverableExportArtifact:
    """A durable export record and its safe user-downloadable artifact."""

    content: bytes
    media_type: str
    filename: str
    storage_key: str
    download_path: str
    export_id: str
    version_number: int


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def get_deliverable_sections_with_versions(db: Session, deliverable_id: str) -> list[dict]:
    """Read the exact approved version for each section, never its newest draft."""
    sections = list(
        db.scalars(
            select(DeliverableSection)
            .where(DeliverableSection.deliverable_id == deliverable_id)
            .where(DeliverableSection.approved_version_id.is_not(None))
            .order_by(DeliverableSection.sort_order, DeliverableSection.section_key)
        ).all()
    )

    result: list[dict] = []
    for section in sections:
        approved_version = db.get(SectionVersion, section.approved_version_id)
        # The FK protects normal operation; this guard prevents a malformed
        # historical row from shipping a different section's body.
        if approved_version is None or approved_version.deliverable_section_id != section.id:
            continue
        content_markdown = approved_version.content_markdown or ""
        result.append(
            {
                "deliverable_section_id": section.id,
                "section_key": section.section_key,
                "title": section.title,
                "sort_order": int(section.sort_order or 0),
                "section_version_id": approved_version.id,
                "version_number": approved_version.version_number,
                "content_markdown": content_markdown,
                "content_sha256": _sha256(content_markdown.encode("utf-8")),
            }
        )
    return result


def _snapshot_hash(sections: list[dict]) -> str:
    return _sha256(
        json.dumps(
            sections,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _next_export_version(db: Session, deliverable_id: str) -> int:
    latest = db.scalar(
        select(func.max(DeliverableExport.version_number)).where(
            DeliverableExport.deliverable_id == deliverable_id
        )
    )
    return int(latest or 0) + 1


def _export_filename(record: DeliverableExport, artifact_format: str) -> str:
    return f"deliverable-{record.deliverable_id}-v{record.version_number}.{artifact_format}"


def _storage_object_name(record: DeliverableExport, artifact_format: str) -> str:
    return (
        f"exports/{record.deliverable_id}/v{record.version_number}/"
        f"{_export_filename(record, artifact_format)}"
    )


def _validate_format(artifact_format: str) -> str:
    normalized = artifact_format.lower().strip()
    if normalized not in SUPPORTED_EXPORT_FORMATS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported export format")
    return normalized


def render_markdown_to_pdf(sections: list[dict]) -> bytes:
    """Render an immutable approved snapshot into a PDF document."""
    from io import BytesIO

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72,
    )
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle("CustomTitle", parent=styles["Title"], fontSize=20, spaceAfter=20)
    story.append(Paragraph("BidPilot Deliverable", title_style))
    story.append(HRFlowable(width="100%", thickness=1, color="#ccc"))
    story.append(Spacer(1, 12))

    heading_style = ParagraphStyle(
        "SectionHead",
        parent=styles["Heading2"],
        fontSize=14,
        spaceBefore=16,
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "PDFBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=12,
    )

    for section in sections:
        title = section.get("title") or section.get("section_key", "Untitled")
        story.append(Paragraph(html.escape(title), heading_style))
        for paragraph in str(section.get("content_markdown") or "").split("\n\n"):
            paragraph = paragraph.strip()
            if paragraph:
                story.append(Paragraph(html.escape(paragraph), body_style))
        story.append(Spacer(1, 6))

    document.build(story)
    return buffer.getvalue()


def _public_sections(record: DeliverableExport) -> list[ApprovedSectionSnapshotRead]:
    return [
        ApprovedSectionSnapshotRead(
            deliverable_section_id=item["deliverable_section_id"],
            section_key=item["section_key"],
            title=item["title"],
            section_version_id=item["section_version_id"],
            version_number=int(item["version_number"]),
            content_sha256=item["content_sha256"],
        )
        for item in record.approved_versions_json
    ]


def deliverable_export_read(record: DeliverableExport) -> DeliverableExportRead:
    generated = record.status == "generated"
    return DeliverableExportRead(
        id=record.id,
        project_id=record.project_id,
        deliverable_id=record.deliverable_id,
        version_number=record.version_number,
        status=record.status,
        snapshot_hash=record.snapshot_hash,
        approved_sections=_public_sections(record),
        docx_download_path=(f"/export/records/{record.id}/docx" if generated and record.docx_storage_key else None),
        pdf_download_path=(f"/export/records/{record.id}/pdf" if generated and record.pdf_storage_key else None),
        docx_sha256=record.docx_sha256,
        pdf_sha256=record.pdf_sha256,
        failure_code=record.failure_code,
        created_at=record.created_at,
        completed_at=record.completed_at,
    )


def create_deliverable_export_command(
    db: Session,
    *,
    deliverable_id: str,
    current_user: CurrentUser,
    client_request_id: str | None = None,
) -> DeliverableExport:
    """Persist and render a versioned snapshot of currently approved sections."""
    deliverable = require_deliverable_capability(
        db,
        current_user=current_user,
        deliverable_id=deliverable_id,
        capability="deliverables.export",
    )

    if client_request_id:
        prior_request = db.scalar(
            select(DeliverableExport)
            .where(DeliverableExport.requested_by_user_id == current_user.id)
            .where(DeliverableExport.client_request_id == client_request_id)
            .limit(1)
        )
        if prior_request is not None:
            if prior_request.deliverable_id != deliverable_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "export_client_request_reused",
                        "message": "This client request id already belongs to another deliverable export.",
                    },
                )
            return prior_request

    # Serialize concurrent exports for the same deliverable so version numbers
    # and snapshot fingerprints remain deterministic under retries.
    locked_deliverable = db.scalar(
        select(Deliverable)
        .where(Deliverable.id == deliverable.id)
        .with_for_update()
    )
    if locked_deliverable is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deliverable not found")

    snapshot = get_deliverable_sections_with_versions(db, locked_deliverable.id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "approved_content_required",
                "message": "No approved sections with content are available to export.",
            },
        )
    snapshot_hash = _snapshot_hash(snapshot)
    existing = db.scalar(
        select(DeliverableExport)
        .where(DeliverableExport.deliverable_id == locked_deliverable.id)
        .where(DeliverableExport.snapshot_hash == snapshot_hash)
        .limit(1)
    )
    if existing is not None:
        return existing

    record = DeliverableExport(
        project_id=locked_deliverable.project_id,
        deliverable_id=locked_deliverable.id,
        version_number=_next_export_version(db, locked_deliverable.id),
        status="generating",
        snapshot_hash=snapshot_hash,
        approved_versions_json=snapshot,
        requested_by_user_id=current_user.id,
        client_request_id=client_request_id,
    )
    db.add(record)
    db.flush()

    try:
        from app.adapters.export import render_markdown_to_docx

        docx_bytes = render_markdown_to_docx(snapshot)
        pdf_bytes = render_markdown_to_pdf(snapshot)
        record.docx_storage_key = upload_bytes(
            locked_deliverable.project_id,
            _storage_object_name(record, "docx"),
            docx_bytes,
            MEDIA_TYPES["docx"],
        )
        record.pdf_storage_key = upload_bytes(
            locked_deliverable.project_id,
            _storage_object_name(record, "pdf"),
            pdf_bytes,
            MEDIA_TYPES["pdf"],
        )
        record.docx_sha256 = _sha256(docx_bytes)
        record.pdf_sha256 = _sha256(pdf_bytes)
        record.status = "generated"
        record.completed_at = _utcnow()
        locked_deliverable.export_status = "exported"
        locked_deliverable.export_storage_key = record.docx_storage_key
        record_audit_event(
            db,
            project_id=locked_deliverable.project_id,
            event_type="deliverable.exported",
            actor_type="user",
            actor_id=current_user.id,
            payload={
                "deliverable_id": locked_deliverable.id,
                "export_id": record.id,
                "version_number": record.version_number,
                "snapshot_hash": record.snapshot_hash,
                "docx_sha256": record.docx_sha256,
                "pdf_sha256": record.pdf_sha256,
            },
        )
        db.commit()
    except Exception as exc:
        # Do not expose storage/provider details to the browser, but preserve a
        # durable failed export state and an audit record for operators.
        record.status = "failed"
        record.failure_code = "artifact_storage_unavailable"
        record.completed_at = _utcnow()
        record_audit_event(
            db,
            project_id=locked_deliverable.project_id,
            event_type="deliverable.export_failed",
            actor_type="user",
            actor_id=current_user.id,
            payload={
                "deliverable_id": locked_deliverable.id,
                "export_id": record.id,
                "failure_code": record.failure_code,
            },
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "artifact_storage_unavailable",
                "message": "The approved export snapshot could not be stored. Retry with a new request id.",
            },
        ) from exc

    db.refresh(record)
    return record


def list_deliverable_exports_query(
    db: Session,
    *,
    deliverable_id: str,
    current_user: CurrentUser,
) -> list[DeliverableExportRead]:
    require_deliverable_capability(
        db,
        current_user=current_user,
        deliverable_id=deliverable_id,
        capability="project.read",
    )
    records = list(
        db.scalars(
            select(DeliverableExport)
            .where(DeliverableExport.deliverable_id == deliverable_id)
            .order_by(DeliverableExport.version_number.desc())
        ).all()
    )
    return [deliverable_export_read(record) for record in records]


def get_deliverable_export_query(
    db: Session,
    *,
    export_id: str,
    current_user: CurrentUser,
) -> DeliverableExport:
    record = db.get(DeliverableExport, export_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deliverable export not found")
    require_deliverable_capability(
        db,
        current_user=current_user,
        deliverable_id=record.deliverable_id,
        capability="project.read",
    )
    return record


def download_deliverable_export_query(
    db: Session,
    *,
    export_id: str,
    artifact_format: str,
    current_user: CurrentUser,
) -> tuple[bytes, str, str, DeliverableExport]:
    artifact_format = _validate_format(artifact_format)
    record = get_deliverable_export_query(db, export_id=export_id, current_user=current_user)
    if record.status != "generated":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "export_not_ready",
                "message": "This export snapshot is not available for download.",
            },
        )
    storage_key = record.docx_storage_key if artifact_format == "docx" else record.pdf_storage_key
    if not storage_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export artifact is unavailable")
    try:
        content = download_storage_key(storage_key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "artifact_storage_unavailable",
                "message": "The export artifact storage is temporarily unavailable.",
            },
        ) from exc
    return content, MEDIA_TYPES[artifact_format], _export_filename(record, artifact_format), record


def generate_deliverable_export_command(
    db: Session,
    *,
    deliverable_id: str,
    artifact_format: str,
    current_user: CurrentUser,
    require_approved: bool,
) -> DeliverableExportArtifact:
    """Compatibility command used by existing tools and direct download routes."""
    _validate_format(artifact_format)
    # Retained for the existing callers. The snapshot builder always includes
    # approved content only, independent of the old boolean's value.
    _ = require_approved
    record = create_deliverable_export_command(
        db,
        deliverable_id=deliverable_id,
        current_user=current_user,
    )
    content, media_type, filename, record = download_deliverable_export_query(
        db,
        export_id=record.id,
        artifact_format=artifact_format,
        current_user=current_user,
    )
    storage_key = record.docx_storage_key if artifact_format == "docx" else record.pdf_storage_key
    assert storage_key is not None
    return DeliverableExportArtifact(
        content=content,
        media_type=media_type,
        filename=filename,
        storage_key=storage_key,
        download_path=f"/export/records/{record.id}/{artifact_format}",
        export_id=record.id,
        version_number=record.version_number,
    )


__all__ = [
    "DeliverableExportArtifact",
    "create_deliverable_export_command",
    "deliverable_export_read",
    "download_deliverable_export_query",
    "generate_deliverable_export_command",
    "get_deliverable_export_query",
    "get_deliverable_sections_with_versions",
    "list_deliverable_exports_query",
]
