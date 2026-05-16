import math
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Bundle, SourceDocument


def list_documents_by_bundle(db: Session, bundle_id: str) -> list[SourceDocument]:
    stmt = select(SourceDocument).where(SourceDocument.bundle_id == bundle_id).order_by(SourceDocument.original_filename)
    return list(db.scalars(stmt).all())


def list_documents_paginated(db: Session, bundle_id: str, page: int = 1, page_size: int = 20) -> tuple[list[SourceDocument], int]:
    """Paginated query for documents in a bundle. Returns (docs, total)."""
    total = db.scalar(select(func.count()).select_from(SourceDocument).where(SourceDocument.bundle_id == bundle_id)) or 0
    docs = db.scalars(
        select(SourceDocument)
        .where(SourceDocument.bundle_id == bundle_id)
        .order_by(SourceDocument.original_filename)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(docs), total


def create_source_document(db: Session, doc: SourceDocument) -> SourceDocument:
    db.add(doc)
    db.flush()
    return doc


def get_bundle_project_id(db: Session, bundle_id: str) -> str | None:
    bundle = db.get(Bundle, bundle_id)
    return bundle.project_id if bundle else None


def get_document_by_id(db: Session, document_id: str) -> SourceDocument | None:
    return db.get(SourceDocument, document_id)
