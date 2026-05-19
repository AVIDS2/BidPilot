from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db

from .schemas import ParsedAssetRead
from .service import get_asset_query, list_assets_query

router = APIRouter(prefix="/parsed-assets", tags=["parsed-assets"])


@router.get("", response_model=list[ParsedAssetRead])
def list_parsed_assets(source_document_id: str, db: Session = Depends(get_db)) -> list[ParsedAssetRead]:
    return list_assets_query(db, source_document_id)


@router.get("/{asset_id}", response_model=ParsedAssetRead)
def get_parsed_asset(asset_id: str, db: Session = Depends(get_db)) -> ParsedAssetRead:
    return get_asset_query(db, asset_id)
