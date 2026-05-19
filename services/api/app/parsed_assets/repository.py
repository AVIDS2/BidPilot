from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ParsedAsset


def list_assets_by_document(db: Session, source_document_id: str) -> list[ParsedAsset]:
    stmt = (
        select(ParsedAsset)
        .where(ParsedAsset.source_document_id == source_document_id)
        .order_by(ParsedAsset.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def get_parsed_asset(db: Session, asset_id: str) -> ParsedAsset | None:
    return db.get(ParsedAsset, asset_id)
