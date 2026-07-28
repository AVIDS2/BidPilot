from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .schemas import DeliverableExportCreate, DeliverableExportRead
from .service import (
    create_deliverable_export_command,
    deliverable_export_read,
    download_deliverable_export_query,
    generate_deliverable_export_command,
    get_deliverable_export_query,
    list_deliverable_exports_query,
)

router = APIRouter(prefix="/export", tags=["export"])


@router.post(
    "/deliverables/{deliverable_id}",
    response_model=DeliverableExportRead,
    status_code=201,
)
def create_deliverable_export(
    deliverable_id: str,
    payload: DeliverableExportCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> DeliverableExportRead:
    record = create_deliverable_export_command(
        db,
        deliverable_id=deliverable_id,
        current_user=current_user,
        client_request_id=payload.client_request_id,
    )
    return deliverable_export_read(record)


@router.get("/deliverables/{deliverable_id}", response_model=list[DeliverableExportRead])
def list_deliverable_exports(
    deliverable_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[DeliverableExportRead]:
    return list_deliverable_exports_query(
        db,
        deliverable_id=deliverable_id,
        current_user=current_user,
    )


@router.get("/records/{export_id}", response_model=DeliverableExportRead)
def get_deliverable_export(
    export_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> DeliverableExportRead:
    return deliverable_export_read(
        get_deliverable_export_query(db, export_id=export_id, current_user=current_user)
    )


@router.get("/records/{export_id}/{artifact_format}")
def download_deliverable_export(
    export_id: str,
    artifact_format: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> Response:
    content, media_type, filename, _record = download_deliverable_export_query(
        db,
        export_id=export_id,
        artifact_format=artifact_format,
        current_user=current_user,
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


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
        require_approved=True,
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
        require_approved=True,
    )

    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={"Content-Disposition": f"attachment; filename={artifact.filename}"},
    )
