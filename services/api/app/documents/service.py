import hashlib
import uuid
from sqlalchemy.orm import Session

from app.audit.service import record_audit_event
from app.models import SourceDocument

from .repository import create_source_document, get_bundle_project_id, get_document_by_id, list_documents_by_bundle, list_documents_paginated
from .schemas import DocumentsPaginatedResponse, SourceDocumentRead


def list_documents_query(db: Session, bundle_id: str) -> list[SourceDocumentRead]:
    docs = list_documents_by_bundle(db, bundle_id)
    return [
        SourceDocumentRead(
            id=d.id,
            bundle_id=d.bundle_id,
            storage_key=d.storage_key,
            mime_type=d.mime_type,
            original_filename=d.original_filename,
            parse_status=d.parse_status,
        )
        for d in docs
    ]


def list_documents_paginated_query(db: Session, bundle_id: str, page: int = 1, page_size: int = 20) -> DocumentsPaginatedResponse:
    """Paginated document listing for large bundles."""
    import math
    docs, total = list_documents_paginated(db, bundle_id, page, page_size)
    items = [
        SourceDocumentRead(
            id=d.id,
            bundle_id=d.bundle_id,
            storage_key=d.storage_key,
            mime_type=d.mime_type,
            original_filename=d.original_filename,
            parse_status=d.parse_status,
        )
        for d in docs
    ]
    return DocumentsPaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)) if total > 0 else 1,
    )


def upload_document_command(
    db: Session,
    bundle_id: str,
    filename: str,
    content_type: str,
    data: bytes,
) -> SourceDocumentRead:
    """Upload a file to MinIO and create a SourceDocument record."""
    project_id = get_bundle_project_id(db, bundle_id)
    if project_id is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Bundle not found")

    # Store in MinIO
    from app.adapters.storage import upload_bytes

    object_name = f"{bundle_id}/{filename}"
    storage_key = upload_bytes(project_id, object_name, data, content_type)

    # Create DB record
    checksum = hashlib.sha256(data).hexdigest()
    doc = SourceDocument(
        bundle_id=bundle_id,
        storage_key=storage_key,
        mime_type=content_type,
        checksum=checksum,
        original_filename=filename,
        parse_status="pending",
    )
    doc = create_source_document(db, doc)

    # Record audit event
    record_audit_event(db, project_id=project_id, event_type="document.uploaded", payload={"document_id": doc.id, "filename": filename})
    db.commit()

    return SourceDocumentRead(
        id=doc.id,
        bundle_id=doc.bundle_id,
        storage_key=doc.storage_key,
        mime_type=doc.mime_type,
        original_filename=doc.original_filename,
        parse_status=doc.parse_status,
    )


def download_document_command(db: Session, document_id: str) -> tuple[bytes, str, str] | None:
    """Download a document from MinIO. Returns (data, filename, content_type) or None."""
    doc = get_document_by_id(db, document_id)
    if doc is None:
        return None

    project_id = get_bundle_project_id(db, doc.bundle_id)
    if project_id is None:
        return None

    # Parse storage_key: "bucket/object_name"
    parts = doc.storage_key.split("/", 1)
    object_name = parts[1] if len(parts) > 1 else doc.storage_key

    from app.adapters.storage import download_bytes

    try:
        data = download_bytes(project_id, object_name)
    except Exception:
        return None

    return data, doc.original_filename, doc.mime_type
