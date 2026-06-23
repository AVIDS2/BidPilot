from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.auth.dependencies import require_auth
from app.auth.schemas import CurrentUser
from app.db import get_db
from app.models import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "read": n.read,
            "link": n.link,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in rows
    ]


@router.patch("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_notification_read(
    notification_id: str,
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Response:
    n = db.get(Notification, notification_id)
    if n and n.user_id == user.id:
        n.read = True
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_notifications_read(
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> Response:
    db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read == False)
        .values(read=True)
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
