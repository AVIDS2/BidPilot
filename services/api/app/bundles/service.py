from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.audit.service import record_audit_event
from app.celery_client import celery
from app.models import Bundle

from .repository import create_bundle, get_bundle, list_bundles_by_project
from .schemas import BundleCreate, BundleRead


def register_bundle_command(db: Session, payload: BundleCreate) -> BundleRead:
    bundle = Bundle(
        project_id=payload.project_id,
        label=payload.label,
        source_type=payload.source_type,
    )
    bundle = create_bundle(db, bundle)
    # Dispatch async ingest task
    celery.send_task("worker.ingest_bundle", args=[bundle.id])
    # Record audit event
    record_audit_event(db, project_id=payload.project_id, event_type="bundle.registered", payload={"bundle_id": bundle.id, "label": payload.label})
    db.commit()
    return BundleRead(
        id=bundle.id,
        project_id=bundle.project_id,
        label=bundle.label,
        source_type=bundle.source_type,
        ingest_status=bundle.ingest_status,
    )


def reingest_bundle_command(db: Session, bundle_id: str) -> BundleRead:
    bundle = get_bundle(db, bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Bundle not found")
    # Reset status and re-dispatch
    bundle.ingest_status = "queued"
    db.commit()
    db.refresh(bundle)
    celery.send_task("worker.ingest_bundle", args=[bundle.id])
    record_audit_event(db, project_id=bundle.project_id, event_type="bundle.reingest", payload={"bundle_id": bundle.id})
    db.commit()
    return BundleRead(
        id=bundle.id,
        project_id=bundle.project_id,
        label=bundle.label,
        source_type=bundle.source_type,
        ingest_status=bundle.ingest_status,
    )


def list_bundles_query(db: Session, project_id: str) -> list[BundleRead]:
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
