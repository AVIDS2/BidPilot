from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .schemas import CollaborationBoardRead
from .service import get_collaboration_board_query


router = APIRouter(prefix="/collaboration", tags=["collaboration"])


@router.get("/projects/{project_id}/board", response_model=CollaborationBoardRead)
def get_collaboration_board(
    project_id: str,
    limit: int = 250,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> CollaborationBoardRead:
    return get_collaboration_board_query(
        db,
        project_id=project_id,
        current_user=current_user,
        limit=limit,
    )
