from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import get_current_user
from app.db import get_db

from .schemas import BidReadinessSummary, ReadinessPackRead
from .service import (
    download_readiness_pack_query,
    generate_readiness_pack_command,
    get_readiness_summary_query,
)

router = APIRouter(prefix="/readiness", tags=["readiness"])


@router.get("/projects/{project_id}", response_model=BidReadinessSummary)
def get_project_readiness(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BidReadinessSummary:
    return get_readiness_summary_query(db, project_id, current_user=current_user)


@router.post(
    "/projects/{project_id}/packs",
    response_model=ReadinessPackRead,
    status_code=status.HTTP_201_CREATED,
)
def generate_readiness_pack(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ReadinessPackRead:
    return generate_readiness_pack_command(
        db,
        project_id,
        current_user=current_user,
        actor_id=current_user.id,
    )


@router.get("/packs/{pack_id}/{artifact_format}")
def download_readiness_pack(
    pack_id: str,
    artifact_format: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    data, media_type, filename = download_readiness_pack_query(
        db,
        pack_id,
        artifact_format,
        current_user=current_user,
    )
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
