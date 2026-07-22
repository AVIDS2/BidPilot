import hashlib
import uuid
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.access.service import require_bundle_capability, require_source_document_capability
from app.audit.service import record_audit_event
from app.auth.schemas import CurrentUser
from app.models import SourceDocument

from .repository import create_source_document, list_documents_by_bundle, list_documents_paginated
from .schemas import DocumentsPaginatedResponse, SourceDocumentRead


def list_documents_query(
    db: Session,
    bundle_id: str,
    current_user: CurrentUser,
) -> list[SourceDocumentRead]:
    require_bundle_capability(
        db,
        current_user=current_user,
        bundle_id=bundle_id,
        capability="project.read",
    )
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


def list_documents_paginated_query(
    db: Session,
    bundle_id: str,
    page: int,
    page_size: int,
    current_user: CurrentUser,
) -> DocumentsPaginatedResponse:
    """Paginated document listing for large bundles."""
    import math
    require_bundle_capability(
        db,
        current_user=current_user,
        bundle_id=bundle_id,
        capability="project.read",
    )
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
    current_user: CurrentUser,
    assistant_attachment_id: str | None = None,
) -> SourceDocumentRead:
    """Upload a file to MinIO and create a SourceDocument record."""
    bundle = require_bundle_capability(
        db,
        current_user=current_user,
        bundle_id=bundle_id,
        capability="bundles.write",
    )
    project_id = bundle.project_id
    if bundle.ingest_status in {"queued", "running", "indexing"}:
        raise HTTPException(status_code=409, detail="Wait for the current bundle processing run before uploading more files")

    # Store in MinIO
    from app.adapters.storage import upload_bytes

    object_name = f"{bundle_id}/{uuid.uuid4().hex}-{_safe_filename(filename)}"
    storage_key = upload_bytes(project_id, object_name, data, content_type)
    staged_storage_key: str | None = None
    try:
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
        bundle.ingest_status = "ready_to_ingest"

        if assistant_attachment_id:
            from app.assistant.attachments import link_staged_attachment_to_document

            staged_storage_key = link_staged_attachment_to_document(
                db,
                current_user=current_user,
                attachment_id=assistant_attachment_id,
                document=doc,
                project_id=project_id,
            )

        # Record audit event
        record_audit_event(
            db,
            project_id=project_id,
            event_type="document.uploaded",
            actor_type="user",
            actor_id=current_user.id,
            payload={"document_id": doc.id, "filename": filename},
        )
        db.commit()
    except Exception:
        db.rollback()
        _delete_storage_key_quietly(storage_key)
        raise

    if staged_storage_key and assistant_attachment_id:
        from app.assistant.attachments import delete_staged_attachment_storage

        delete_staged_attachment_storage(db, assistant_attachment_id)

    return SourceDocumentRead(
        id=doc.id,
        bundle_id=doc.bundle_id,
        storage_key=doc.storage_key,
        mime_type=doc.mime_type,
        original_filename=doc.original_filename,
        parse_status=doc.parse_status,
    )


def _safe_filename(filename: str) -> str:
    value = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    return value[:240] or "untitled"


def _delete_storage_key_quietly(storage_key: str) -> None:
    try:
        from app.adapters.storage import delete_storage_key

        delete_storage_key(storage_key)
    except Exception:
        # The object is private and the durable database transaction is the source
        # of truth. A later storage lifecycle job can remove a rare orphan.
        return


def download_document_command(
    db: Session,
    document_id: str,
    current_user: CurrentUser,
) -> tuple[bytes, str, str] | None:
    """Download a document from MinIO. Returns (data, filename, content_type) or None."""
    doc = require_source_document_capability(
        db,
        current_user=current_user,
        document_id=document_id,
        capability="project.read",
    )
    bundle = require_bundle_capability(
        db,
        current_user=current_user,
        bundle_id=doc.bundle_id,
        capability="project.read",
    )
    project_id = bundle.project_id

    from app.projects.demo_data import get_builtin_demo_document

    builtin_document = get_builtin_demo_document(doc.storage_key)
    if builtin_document is not None:
        return (
            builtin_document.content.encode("utf-8"),
            doc.original_filename,
            doc.mime_type,
        )

    # Parse storage_key: "bucket/object_name"
    parts = doc.storage_key.split("/", 1)
    object_name = parts[1] if len(parts) > 1 else doc.storage_key

    from app.adapters.storage import download_bytes

    try:
        data = download_bytes(project_id, object_name)
    except Exception:
        return None

    return data, doc.original_filename, doc.mime_type
