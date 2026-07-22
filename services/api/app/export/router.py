from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .service import generate_deliverable_export_command

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/deliverables/{deliverable_id}/docx")
def export_deliverable_docx(
    deliverable_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> Response:
    """Export a deliverable as a DOCX file."""
    artifact = generate_deliverable_export_command(
        db,
        deliverable_id=deliverable_id,
        artifact_format="docx",
        current_user=current_user,
        require_approved=False,
    )

    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={"Content-Disposition": f"attachment; filename={artifact.filename}"},
    )


@router.get("/deliverables/{deliverable_id}/pdf")
def export_deliverable_pdf(
    deliverable_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> Response:
    """Export a deliverable as a PDF file."""
    artifact = generate_deliverable_export_command(
        db,
        deliverable_id=deliverable_id,
        artifact_format="pdf",
        current_user=current_user,
        require_approved=False,
    )

    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={"Content-Disposition": f"attachment; filename={artifact.filename}"},
    )
