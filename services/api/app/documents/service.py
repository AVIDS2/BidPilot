import hashlib
import uuid
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.access.service import require_bundle_capability, require_source_document_capability
from app.audit.service import record_audit_event
from app.auth.schemas import CurrentUser
from app.celery_client import celery
from app.models import SourceDocument
from app.usage.schemas import ProviderSource
from app.usage.service import EMBEDDING_INDEX_STARTED, check_indexing_quota, record_usage_event
from contracts.document_ingestion import (
    BundleIngestStatus,
    DocumentIndexStatus,
    DocumentParseStatus,
    MAX_STORED_ARTIFACT_BYTES,
    STORED_ARTIFACT_MIME_TYPES,
    canonical_source_document_mime_type,
    source_document_is_parseable,
    source_document_validation_error,
)

from .repository import (
    create_source_document,
    get_document_by_id_for_update,
    list_documents_by_bundle,
    list_documents_paginated,
)
from .schemas import DocumentsPaginatedResponse, SourceDocumentRead


def _document_to_read(document: SourceDocument, *, ingest_queued: bool = False) -> SourceDocumentRead:
    return SourceDocumentRead(
        id=document.id,
        bundle_id=document.bundle_id,
        storage_key=document.storage_key,
        mime_type=document.mime_type,
        original_filename=document.original_filename,
        source_url=document.source_url,
        ingest_queued=ingest_queued,
        parse_status=document.parse_status,
        parse_attempt_count=document.parse_attempt_count,
        parser_name=document.parser_name,
        parser_version=document.parser_version,
        parse_error_code=document.parse_error_code,
        parse_error_detail=document.parse_error_detail,
        parse_retryable=document.parse_retryable,
        index_status=document.index_status,
        index_error_code=document.index_error_code,
        version_number=document.version_number,
        supersedes_document_id=document.supersedes_document_id,
    )


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
        _document_to_read(d)
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
        _document_to_read(d)
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
    supersedes_document_id: str | None = None,
    source_url: str | None = None,
    queue_ingest: bool = True,
) -> SourceDocumentRead:
    """Upload one immutable source-document version and optionally queue its bundle."""
    bundle = require_bundle_capability(
        db,
        current_user=current_user,
        bundle_id=bundle_id,
        capability="bundles.write",
    )
    project_id = bundle.project_id
    if bundle.ingest_status in {
        BundleIngestStatus.QUEUED.value,
        BundleIngestStatus.RUNNING.value,
        BundleIngestStatus.INDEXING.value,
    }:
        raise HTTPException(status_code=409, detail="Wait for the current bundle processing run before uploading more files")

    safe_filename = _safe_filename(filename)
    mime_type = canonical_source_document_mime_type(filename=safe_filename, content_type=content_type)
    if mime_type is None:
        raise HTTPException(status_code=415, detail="Unsupported document type. Upload PDF, DOCX, XLSX, CSV, TXT, or Markdown.")
    validation_error = source_document_validation_error(data=data, mime_type=mime_type)
    if validation_error is not None:
        status_code = 413 if validation_error == "document_too_large" else 422
        raise HTTPException(status_code=status_code, detail=validation_error)

    parseable = source_document_is_parseable(mime_type)
    should_queue_ingest = queue_ingest and parseable
    if should_queue_ingest:
        check_indexing_quota(db, current_user.id, current_user.org_id, ProviderSource.OFFICIAL)

    superseded_document: SourceDocument | None = None
    if supersedes_document_id:
        superseded_document = get_document_by_id_for_update(db, supersedes_document_id)
        if superseded_document is None or superseded_document.bundle_id != bundle_id:
            raise HTTPException(status_code=422, detail="Replacement document must belong to the same bundle")

    # Store in MinIO
    from app.adapters.storage import upload_bytes

    object_name = f"{bundle_id}/{uuid.uuid4().hex}-{safe_filename}"
    storage_key = upload_bytes(project_id, object_name, data, mime_type)
    staged_storage_key: str | None = None
    try:
        # Create DB record
        checksum = hashlib.sha256(data).hexdigest()
        doc = SourceDocument(
            bundle_id=bundle_id,
            storage_key=storage_key,
            mime_type=mime_type,
            checksum=checksum,
            original_filename=safe_filename,
            source_url=source_url.strip()[:2048] if source_url and source_url.strip() else None,
            parse_status=(DocumentParseStatus.PENDING.value if parseable else DocumentParseStatus.NOT_APPLICABLE.value),
            index_status=(DocumentIndexStatus.PENDING.value if parseable else DocumentIndexStatus.NOT_APPLICABLE.value),
            parse_retryable=parseable,
            version_number=(superseded_document.version_number + 1) if superseded_document else 1,
            supersedes_document_id=superseded_document.id if superseded_document else None,
        )
        doc = create_source_document(db, doc)
        if parseable:
            bundle.ingest_status = BundleIngestStatus.READY_TO_INGEST.value
        elif not any(
            source_document_is_parseable(item.mime_type)
            for item in list_documents_by_bundle(db, bundle_id)
        ):
            # Downloadable supporting artifacts (for example bidder software
            # ZIPs) are durable project material, not failed text parsing.
            # Agent-created bundles start as ready_to_ingest, so rely on their
            # actual contents instead of the creation-time bundle status.
            bundle.ingest_status = BundleIngestStatus.INGESTED.value

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
            payload={
                "document_id": doc.id,
                "filename": safe_filename,
                "source_url": doc.source_url,
                "version_number": doc.version_number,
                "supersedes_document_id": doc.supersedes_document_id,
                "parse_applicable": parseable,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        _delete_storage_key_quietly(storage_key)
        if supersedes_document_id:
            raise HTTPException(
                status_code=409,
                detail="This document version already has a replacement",
            ) from exc
        raise
    except Exception:
        db.rollback()
        _delete_storage_key_quietly(storage_key)
        raise

    if staged_storage_key and assistant_attachment_id:
        from app.assistant.attachments import delete_staged_attachment_storage

        delete_staged_attachment_storage(db, assistant_attachment_id)

    if not should_queue_ingest:
        return _document_to_read(doc)

    bundle.ingest_status = BundleIngestStatus.QUEUED.value
    db.commit()
    db.refresh(bundle)
    try:
        celery.send_task("worker.ingest_bundle", args=[bundle.id])
    except Exception:
        # The source document is durable. Restore a retryable status instead of
        # showing a forever-queued bundle when the broker is unavailable.
        bundle.ingest_status = BundleIngestStatus.READY_TO_INGEST.value
        record_audit_event(
            db,
            project_id=project_id,
            event_type="bundle.ingest_dispatch_failed",
            actor_type="system",
            actor_id=current_user.id,
            payload={"bundle_id": bundle.id, "action": "upload_document"},
        )
        db.commit()
        return _document_to_read(doc)

    record_usage_event(
        db,
        user_id=current_user.id,
        org_id=current_user.org_id,
        project_id=project_id,
        event_type=EMBEDDING_INDEX_STARTED,
        provider_source=ProviderSource.OFFICIAL,
        metadata_json={"bundle_id": bundle.id, "action": "upload_document"},
    )
    record_audit_event(
        db,
        project_id=project_id,
        event_type="bundle.ingest_requested",
        actor_type="user",
        actor_id=current_user.id,
        payload={"bundle_id": bundle.id, "document_id": doc.id},
    )
    db.commit()
    return _document_to_read(doc, ingest_queued=True)


def upload_artifact_file_command(
    db: Session,
    *,
    bundle_id: str,
    filename: str,
    content_type: str,
    file_path: str,
    byte_count: int,
    checksum: str,
    signature: bytes,
    current_user: CurrentUser,
    source_url: str | None = None,
) -> SourceDocumentRead:
    """Persist a large, non-parseable remote artifact from a local file.

    Remote ZIP/RAR/7z packages are kept as project material but never enter
    text extraction. Using MinIO's file upload path prevents a slow public
    download from being duplicated in Worker memory.
    """
    bundle = require_bundle_capability(
        db,
        current_user=current_user,
        bundle_id=bundle_id,
        capability="bundles.write",
    )
    if bundle.ingest_status in {
        BundleIngestStatus.QUEUED.value,
        BundleIngestStatus.RUNNING.value,
        BundleIngestStatus.INDEXING.value,
    }:
        raise HTTPException(status_code=409, detail="Wait for the current bundle processing run before uploading more files")

    safe_filename = _safe_filename(filename)
    mime_type = canonical_source_document_mime_type(filename=safe_filename, content_type=content_type)
    if mime_type not in STORED_ARTIFACT_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Remote file is not a supported downloadable artifact")
    if byte_count <= 0:
        raise HTTPException(status_code=422, detail="empty_document")
    if byte_count > MAX_STORED_ARTIFACT_BYTES:
        raise HTTPException(status_code=413, detail="document_too_large")
    validation_error = source_document_validation_error(data=signature, mime_type=mime_type)
    if validation_error is not None:
        status_code = 413 if validation_error == "document_too_large" else 422
        raise HTTPException(status_code=status_code, detail=validation_error)

    from app.adapters.storage import upload_file

    object_name = f"{bundle_id}/{uuid.uuid4().hex}-{safe_filename}"
    storage_key = upload_file(bundle.project_id, object_name, file_path, mime_type)
    try:
        doc = create_source_document(
            db,
            SourceDocument(
                bundle_id=bundle_id,
                storage_key=storage_key,
                mime_type=mime_type,
                checksum=checksum,
                original_filename=safe_filename,
                source_url=source_url.strip()[:2048] if source_url and source_url.strip() else None,
                parse_status=DocumentParseStatus.NOT_APPLICABLE.value,
                index_status=DocumentIndexStatus.NOT_APPLICABLE.value,
                parse_retryable=False,
            ),
        )
        if not any(source_document_is_parseable(item.mime_type) for item in list_documents_by_bundle(db, bundle_id)):
            bundle.ingest_status = BundleIngestStatus.INGESTED.value
        record_audit_event(
            db,
            project_id=bundle.project_id,
            event_type="document.uploaded",
            actor_type="user",
            actor_id=current_user.id,
            payload={
                "document_id": doc.id,
                "filename": safe_filename,
                "source_url": doc.source_url,
                "version_number": doc.version_number,
                "parse_applicable": False,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        _delete_storage_key_quietly(storage_key)
        raise
    return _document_to_read(doc)


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
