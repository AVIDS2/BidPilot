from sqlalchemy.orm import Session

from app.access.service import require_parsed_asset_capability, require_source_document_capability
from app.auth.schemas import CurrentUser

from .repository import list_assets_by_document
from .schemas import ParsedAssetRead


def list_assets_query(
    db: Session,
    source_document_id: str,
    current_user: CurrentUser,
) -> list[ParsedAssetRead]:
    require_source_document_capability(
        db,
        current_user=current_user,
        document_id=source_document_id,
        capability="project.read",
    )
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


def get_asset_query(
    db: Session,
    asset_id: str,
    current_user: CurrentUser,
) -> ParsedAssetRead:
    asset = require_parsed_asset_capability(
        db,
        current_user=current_user,
        asset_id=asset_id,
        capability="project.read",
    )
    return ParsedAssetRead(
        id=asset.id,
        source_document_id=asset.source_document_id,
        parser_name=asset.parser_name,
        parser_version=asset.parser_version,
        content_json=asset.content_json,
        layout_json=asset.layout_json,
    )
