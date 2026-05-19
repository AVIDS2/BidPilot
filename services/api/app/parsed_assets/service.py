from sqlalchemy.orm import Session

from .repository import get_parsed_asset, list_assets_by_document
from .schemas import ParsedAssetRead


def list_assets_query(db: Session, source_document_id: str) -> list[ParsedAssetRead]:
    assets = list_assets_by_document(db, source_document_id)
    return [
        ParsedAssetRead(
            id=a.id,
            source_document_id=a.source_document_id,
            parser_name=a.parser_name,
            parser_version=a.parser_version,
            content_json=a.content_json,
            layout_json=a.layout_json,
        )
        for a in assets
    ]


def get_asset_query(db: Session, asset_id: str) -> ParsedAssetRead | None:
    asset = get_parsed_asset(db, asset_id)
    if asset is None:
        return None
    return ParsedAssetRead(
        id=asset.id,
        source_document_id=asset.source_document_id,
        parser_name=asset.parser_name,
        parser_version=asset.parser_version,
        content_json=asset.content_json,
        layout_json=asset.layout_json,
    )
