from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.access.service import require_bundle_capability, require_project_capability
from app.auth.schemas import CurrentUser
from app.audit.service import record_audit_event
from app.celery_client import celery
from app.models import Bundle
from app.usage.schemas import ProviderSource
from app.usage.service import EMBEDDING_INDEX_STARTED, check_indexing_quota, record_usage_event

from .repository import create_bundle, list_bundles_by_project
from .schemas import BundleCreate, BundleRead


def register_bundle_command(
    db: Session,
    payload: BundleCreate,
    current_user: CurrentUser,
) -> BundleRead:
    require_project_capability(
        db,
        current_user=current_user,
        project_id=payload.project_id,
        capability="bundles.write",
    )
    bundle = Bundle(
        project_id=payload.project_id,
        label=payload.label,
        source_type=payload.source_type,
        ingest_status="awaiting_upload",
    )
    bundle = create_bundle(db, bundle)
    # Record audit event
    record_audit_event(
        db,
        project_id=payload.project_id,
        event_type="bundle.registered",
        actor_type="user",
        actor_id=current_user.id,
        payload={"bundle_id": bundle.id, "label": payload.label},
    )
    db.commit()
    return BundleRead(
        id=bundle.id,
        project_id=bundle.project_id,
        label=bundle.label,
        source_type=bundle.source_type,
        ingest_status=bundle.ingest_status,
    )


def reingest_bundle_command(
    db: Session,
    bundle_id: str,
    current_user: CurrentUser,
) -> BundleRead:
    bundle = require_bundle_capability(
        db,
        current_user=current_user,
        bundle_id=bundle_id,
        capability="bundles.write",
    )
    if bundle.ingest_status in {"queued", "running", "indexing"}:
        raise HTTPException(status_code=409, detail="Bundle processing is already in progress")
    if not bundle.source_documents:
        raise HTTPException(status_code=409, detail="Upload at least one document before processing this bundle")
    check_indexing_quota(db, current_user.id, current_user.org_id, ProviderSource.OFFICIAL)
    # Reset status and re-dispatch
    bundle.ingest_status = "queued"
    db.commit()
    db.refresh(bundle)
    record_usage_event(
        db,
        user_id=current_user.id,
        org_id=current_user.org_id,
        project_id=bundle.project_id,
        event_type=EMBEDDING_INDEX_STARTED,
        provider_source=ProviderSource.OFFICIAL,
        metadata_json={"bundle_id": bundle.id, "action": "reingest_bundle"},
    )
    celery.send_task("worker.ingest_bundle", args=[bundle.id])
    record_audit_event(
        db,
        project_id=bundle.project_id,
        event_type="bundle.reingest",
        actor_type="user",
        actor_id=current_user.id,
        payload={"bundle_id": bundle.id},
    )
    db.commit()
    return BundleRead(
        id=bundle.id,
        project_id=bundle.project_id,
        label=bundle.label,
        source_type=bundle.source_type,
        ingest_status=bundle.ingest_status,
    )


def reindex_bundle_command(
    db: Session,
    bundle_id: str,
    current_user: CurrentUser,
) -> BundleRead:
    """Queue a profile refresh that does not parse or recreate bundle data."""
    bundle = require_bundle_capability(
        db,
        current_user=current_user,
        bundle_id=bundle_id,
        capability="bundles.write",
    )
    check_indexing_quota(db, current_user.id, current_user.org_id, ProviderSource.OFFICIAL)
    bundle.ingest_status = "queued"
    record_usage_event(
        db,
        user_id=current_user.id,
        org_id=current_user.org_id,
        project_id=bundle.project_id,
        event_type=EMBEDDING_INDEX_STARTED,
        provider_source=ProviderSource.OFFICIAL,
        metadata_json={"bundle_id": bundle.id, "action": "reindex_bundle"},
    )
    celery.send_task("worker.reindex_bundle", args=[bundle.id])
    record_audit_event(
        db,
        project_id=bundle.project_id,
        event_type="bundle.reindex_requested",
        actor_type="user",
        actor_id=current_user.id,
        payload={"bundle_id": bundle.id},
    )
    db.commit()
    db.refresh(bundle)
    return BundleRead(
        id=bundle.id,
        project_id=bundle.project_id,
        label=bundle.label,
        source_type=bundle.source_type,
        ingest_status=bundle.ingest_status,
    )


def list_bundles_query(
    db: Session,
    project_id: str,
    *,
    current_user: CurrentUser,
) -> list[BundleRead]:
    require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.read",
    )
    bundles = list_bundles_by_project(db, project_id)
    return [
        BundleRead(
            id=b.id,
            project_id=b.project_id,
            label=b.label,
            source_type=b.source_type,
            ingest_status=b.ingest_status,
        )
        for b in bundles
    ]
