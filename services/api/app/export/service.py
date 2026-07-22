from dataclasses import dataclass
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access.service import require_deliverable_capability
from app.audit.service import record_audit_event
from app.auth.schemas import CurrentUser
from app.models import Deliverable, DeliverableSection, SectionVersion


@dataclass(frozen=True)
class DeliverableExportArtifact:
    """A generated export and its safe, user-downloadable route."""

    content: bytes
    media_type: str
    filename: str
    storage_key: str | None
    download_path: str


def get_deliverable_sections_with_versions(db: Session, deliverable_id: str) -> list[dict]:
    """Get approved sections for a deliverable with their latest version content."""
    sections = list(
        db.scalars(
            select(DeliverableSection)
            .where(DeliverableSection.deliverable_id == deliverable_id)
            .where(DeliverableSection.status == "approved")
            .order_by(DeliverableSection.section_key)
        ).all()
    )

    result = []
    for section in sections:
        latest_version = db.scalar(
            select(SectionVersion)
            .where(SectionVersion.deliverable_section_id == section.id)
            .order_by(SectionVersion.version_number.desc())
            .limit(1)
        )
        result.append({
            "title": section.title,
            "content_markdown": latest_version.content_markdown if latest_version else "",
        })
    return result


def render_markdown_to_pdf(sections: list[dict]) -> bytes:
    """Render approved sections to a PDF document using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from io import BytesIO
    import html

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle("CustomTitle", parent=styles["Title"], fontSize=20, spaceAfter=20)
    story.append(Paragraph("BidPilot Deliverable", title_style))
    story.append(HRFlowable(width="100%", thickness=1, color="#ccc"))
    story.append(Spacer(1, 12))

    heading_style = ParagraphStyle("SectionHead", parent=styles["Heading2"], fontSize=14, spaceBefore=16, spaceAfter=8)
    body_style = ParagraphStyle("PDFBody", parent=styles["Normal"], fontSize=10, leading=14, spaceAfter=12)

    for section in sections:
        title = section.get("title") or section.get("section_key", "Untitled")
        story.append(Paragraph(title, heading_style))
        content_md = section.get("content_markdown", "")
        for para in content_md.split("\n\n"):
            para = para.strip()
            if para:
                story.append(Paragraph(html.escape(para), body_style))
        story.append(Spacer(1, 6))

    doc.build(story)
    return buffer.getvalue()


def mark_deliverable_exported(
    db: Session,
    deliverable_id: str,
    storage_key: str | None,
    current_user: CurrentUser,
) -> None:
    """Update deliverable export status after successful export."""
    deliverable = db.get(Deliverable, deliverable_id)
    if deliverable is not None:
        deliverable.export_status = "exported"
        deliverable.export_storage_key = storage_key
        record_audit_event(
            db,
            project_id=deliverable.project_id,
            event_type="deliverable.exported",
            actor_type="user",
            actor_id=current_user.id,
            payload={"deliverable_id": deliverable_id, "storage_key": storage_key},
        )
        db.commit()


def generate_deliverable_export_command(
    db: Session,
    *,
    deliverable_id: str,
    artifact_format: str,
    current_user: CurrentUser,
    require_approved: bool,
) -> DeliverableExportArtifact:
    """Render a deliverable, persist it when storage is available, and audit it."""
    if artifact_format not in {"docx", "pdf"}:
        raise HTTPException(status_code=400, detail="Unsupported export format")
    deliverable = require_deliverable_capability(
        db,
        current_user=current_user,
        deliverable_id=deliverable_id,
        capability="deliverables.export",
    )
    if require_approved and deliverable.status != "approved":
        raise HTTPException(status_code=409, detail="Deliverable must be approved before export")

    sections = get_deliverable_sections_with_versions(db, deliverable_id)
    if not sections:
        raise HTTPException(status_code=404, detail="Deliverable not found or has no approved sections")

    if artifact_format == "docx":
        from app.adapters.export import render_markdown_to_docx

        content = render_markdown_to_docx(sections)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        content = render_markdown_to_pdf(sections)
        media_type = "application/pdf"

    filename = f"deliverable-{deliverable_id}.{artifact_format}"
    storage_key: str | None = None
    try:
        from app.adapters.storage import upload_bytes

        storage_key = upload_bytes(
            deliverable.project_id,
            f"exports/{deliverable_id}/{uuid4().hex}.{artifact_format}",
            content,
            media_type,
        )
    except Exception:
        # The direct download route can regenerate this artifact. Do not claim
        # storage persistence when the object store is unavailable.
        storage_key = None

    mark_deliverable_exported(db, deliverable_id, storage_key, current_user)
    return DeliverableExportArtifact(
        content=content,
        media_type=media_type,
        filename=filename,
        storage_key=storage_key,
        download_path=f"/export/deliverables/{deliverable_id}/{artifact_format}",
    )
