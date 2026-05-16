from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db

from .service import get_deliverable_sections_with_versions, mark_deliverable_exported, render_markdown_to_pdf

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/deliverables/{deliverable_id}/docx")
def export_deliverable_docx(deliverable_id: str, db: Session = Depends(get_db)) -> Response:
    """Export a deliverable as a DOCX file."""
    sections = get_deliverable_sections_with_versions(db, deliverable_id)
    if not sections:
        raise HTTPException(status_code=404, detail="Deliverable not found or has no sections")

    from app.adapters.export import render_markdown_to_docx

    docx_bytes = render_markdown_to_docx(sections)

    # Try to upload to MinIO for persistence
    storage_key = None
    try:
        from app.adapters.storage import upload_bytes
        from app.models import Deliverable
        deliverable = db.get(Deliverable, deliverable_id)
        if deliverable:
            object_name = f"exports/{deliverable_id}/deliverable.docx"
            upload_bytes(deliverable.project_id, object_name, docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            storage_key = f"{deliverable.project_id}/{object_name}"
    except Exception:
        pass  # MinIO not available, still serve the file

    # Mark deliverable as exported
    mark_deliverable_exported(db, deliverable_id, storage_key)

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=deliverable-{deliverable_id}.docx"},
    )


@router.get("/deliverables/{deliverable_id}/pdf")
def export_deliverable_pdf(deliverable_id: str, db: Session = Depends(get_db)) -> Response:
    """Export a deliverable as a PDF file."""
    sections = get_deliverable_sections_with_versions(db, deliverable_id)
    if not sections:
        raise HTTPException(status_code=404, detail="Deliverable not found or has no sections")

    pdf_bytes = render_markdown_to_pdf(sections)

    # Try to upload to MinIO for persistence
    try:
        from app.adapters.storage import upload_bytes
        from app.models import Deliverable
        deliverable = db.get(Deliverable, deliverable_id)
        if deliverable:
            object_name = f"exports/{deliverable_id}/deliverable.pdf"
            upload_bytes(deliverable.project_id, object_name, pdf_bytes, "application/pdf")
    except Exception:
        pass  # MinIO not available, still serve the file

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=deliverable-{deliverable_id}.pdf"},
    )
