from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .schemas import (
    NoticePollRead,
    NoticeProjectConvert,
    NoticeProjectConvertRead,
    NoticeRead,
    NoticeSourceCreate,
    NoticeSourceIngest,
    NoticeSourceRead,
    NoticeSourceUpdate,
    NoticeStatusUpdate,
    NoticeSubscriptionCreate,
    NoticeSubscriptionRead,
    NoticeSubscriptionUpdate,
    RadarOverviewRead,
)
from .service import (
    convert_notice_to_project_command,
    create_notice_source_command,
    create_subscription_command,
    ingest_notice_source_command,
    list_radar_overview_query,
    poll_notice_source_command,
    update_notice_source_command,
    update_notice_status_command,
    update_subscription_command,
)


router = APIRouter(prefix="/radar", tags=["radar"])


@router.get("/overview", response_model=RadarOverviewRead)
def get_overview(
    view: str = Query(default="recommended", pattern="^(recommended|all|intent|tender|saved|ignored)$"),
    query: str | None = Query(default=None, max_length=240),
    notice_type: str | None = Query(default=None, pattern="^(intent|tender|prequalification|rfi|other)$"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> RadarOverviewRead:
    return list_radar_overview_query(
        db,
        current_user=current_user,
        view=view,
        query=query,
        notice_type=notice_type,
    )


@router.post("/sources", response_model=NoticeSourceRead, status_code=status.HTTP_201_CREATED)
def create_source(
    payload: NoticeSourceCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> NoticeSourceRead:
    return create_notice_source_command(db, payload=payload, current_user=current_user)


@router.patch("/sources/{source_id}", response_model=NoticeSourceRead)
def update_source(
    source_id: str,
    payload: NoticeSourceUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> NoticeSourceRead:
    return update_notice_source_command(db, source_id=source_id, payload=payload, current_user=current_user)


@router.post("/sources/{source_id}/poll", response_model=NoticePollRead)
def poll_source(
    source_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> NoticePollRead:
    return poll_notice_source_command(db, source_id=source_id, current_user=current_user)


@router.post("/sources/{source_id}/ingest", response_model=NoticePollRead)
def ingest_source(
    source_id: str,
    payload: NoticeSourceIngest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> NoticePollRead:
    return ingest_notice_source_command(db, source_id=source_id, items=payload.items, current_user=current_user)


@router.post("/subscriptions", response_model=NoticeSubscriptionRead, status_code=status.HTTP_201_CREATED)
def create_subscription(
    payload: NoticeSubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> NoticeSubscriptionRead:
    return create_subscription_command(db, payload=payload, current_user=current_user)


@router.patch("/subscriptions/{subscription_id}", response_model=NoticeSubscriptionRead)
def update_subscription(
    subscription_id: str,
    payload: NoticeSubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> NoticeSubscriptionRead:
    return update_subscription_command(db, subscription_id=subscription_id, payload=payload, current_user=current_user)


@router.patch("/notices/{notice_id}/status", response_model=NoticeRead)
def update_notice_status(
    notice_id: str,
    payload: NoticeStatusUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> NoticeRead:
    return update_notice_status_command(db, notice_id=notice_id, payload=payload, current_user=current_user)


@router.post("/notices/{notice_id}/convert", response_model=NoticeProjectConvertRead)
def convert_notice_to_project(
    notice_id: str,
    payload: NoticeProjectConvert,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> NoticeProjectConvertRead:
    return convert_notice_to_project_command(db, notice_id=notice_id, payload=payload, current_user=current_user)
