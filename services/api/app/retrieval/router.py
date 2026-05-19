from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db

from .schemas import SearchRequest, SearchResult
from .service import search_command

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/search", response_model=list[SearchResult])
def search(payload: SearchRequest, db: Session = Depends(get_db)) -> list[SearchResult]:
    return search_command(db, payload)
