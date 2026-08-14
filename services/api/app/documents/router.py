from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .schemas import DocumentsPaginatedResponse, SourceDocumentRead
from .service import download_document_command, list_documents_paginated_query, upload_document_command

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentsPaginatedResponse)
def list_documents(
    bundle_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> DocumentsPaginatedResponse:
    """List documents in a bundle with pagination support for large bundles."""
    return list_documents_paginated_query(db, bundle_id, page, page_size, current_user)


@router.post("/upload", response_model=SourceDocumentRead, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    bundle_id: str | None = Query(None),
    defer_ingest: bool = Query(False),
    form_bundle_id: str | None = Form(None, alias="bundle_id"),
    assistant_attachment_id: str | None = Form(None),
    supersedes_document_id: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> SourceDocumentRead:
    resolved_bundle_id = form_bundle_id or bundle_id
    if not resolved_bundle_id:
        raise HTTPException(status_code=422, detail="bundle_id is required")
    data = await file.read()
    return upload_document_command(
        db,
        bundle_id=resolved_bundle_id,
        filename=file.filename or "untitled",
        content_type=file.content_type or "application/octet-stream",
        data=data,
        current_user=current_user,
        assistant_attachment_id=assistant_attachment_id,
        supersedes_document_id=supersedes_document_id,
        queue_ingest=not defer_ingest,
    )


@router.get("/{document_id}/download")
def download_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> Response:
    result = download_document_command(db, document_id, current_user)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found")
    data, filename, content_type = result
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}"},
    )
