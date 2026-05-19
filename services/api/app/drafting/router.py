from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db

from .schemas import DraftSectionRequest, DraftSectionResponse, RedraftSectionRequest
from .service import draft_section_command, redraft_section_command

router = APIRouter(prefix="/drafting", tags=["drafting"])


@router.post("/sections", response_model=DraftSectionResponse, status_code=status.HTTP_202_ACCEPTED)
def draft_section(payload: DraftSectionRequest, db: Session = Depends(get_db)) -> DraftSectionResponse:
    return draft_section_command(db, payload)


@router.post("/sections/redraft", response_model=DraftSectionResponse, status_code=status.HTTP_202_ACCEPTED)
def redraft_section(payload: RedraftSectionRequest, db: Session = Depends(get_db)) -> DraftSectionResponse:
    return redraft_section_command(db, payload)
