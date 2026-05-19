from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.db import get_db

from .schemas import DocumentsPaginatedResponse, SourceDocumentRead
from .service import download_document_command, list_documents_paginated_query, list_documents_query, upload_document_command

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentsPaginatedResponse)
def list_documents(
    bundle_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> DocumentsPaginatedResponse:
    """List documents in a bundle with pagination support for large bundles."""
    return list_documents_paginated_query(db, bundle_id, page, page_size)


@router.post("/upload", response_model=SourceDocumentRead, status_code=201)
async def upload_document(
    bundle_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> SourceDocumentRead:
    data = await file.read()
    return upload_document_command(
        db,
        bundle_id=bundle_id,
        filename=file.filename or "untitled",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )


@router.get("/{document_id}/download")
def download_document(document_id: str, db: Session = Depends(get_db)) -> Response:
    result = download_document_command(db, document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found")
    data, filename, content_type = result
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}"},
    )
