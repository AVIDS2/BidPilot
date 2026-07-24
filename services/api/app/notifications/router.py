"""Notification inbox + SSE wake stream."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import SessionLocal, get_db
from app.models import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _serialize(n: Notification) -> dict:
    created = n.created_at.isoformat() if isinstance(n.created_at, datetime) else None
    return {
        "id": n.id,
        "type": n.type,
        "title": n.title,
        "body": n.body,
        "read": n.read,
        "link": n.link,
        "created_at": created,
    }


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
    return [_serialize(n) for n in rows]


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
        .where(Notification.user_id == user.id, Notification.read.is_(False))
        .values(read=True)
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/stream")
async def stream_notifications(
    user: CurrentUser = Depends(require_auth),
    after_created_at: str | None = Query(default=None),
    after_id: str | None = Query(default=None),
) -> StreamingResponse:
    """SSE wake stream for durable notifications (agent_task etc.).

    Short DB polls + heartbeat comments. Clients fall back to REST polling if
    EventSource is unavailable.
    """

    user_id = user.id

    async def event_generator():
        cursor_ts: datetime | None = None
        cursor_id: str | None = after_id
        if after_created_at:
            try:
                cursor_ts = datetime.fromisoformat(after_created_at.replace("Z", "+00:00")).replace(
                    tzinfo=None
                )
            except ValueError:
                cursor_ts = None

        # Seed to "now" so reconnects don't replay the whole inbox unless cursor given.
        if cursor_ts is None and cursor_id is None:
            db = SessionLocal()
            try:
                latest = db.scalar(
                    select(Notification)
                    .where(Notification.user_id == user_id)
                    .order_by(Notification.created_at.desc(), Notification.id.desc())
                    .limit(1)
                )
                if latest is not None:
                    cursor_ts = latest.created_at
                    cursor_id = latest.id
            finally:
                db.close()

        yield 'event: ready\ndata: {"ok": true}\n\n'
        idle_ticks = 0
        while True:
            db = SessionLocal()
            try:
                stmt = select(Notification).where(Notification.user_id == user_id)
                if cursor_ts is not None and cursor_id is not None:
                    stmt = stmt.where(
                        or_(
                            Notification.created_at > cursor_ts,
                            and_(
                                Notification.created_at == cursor_ts,
                                Notification.id > cursor_id,
                            ),
                        )
                    )
                elif cursor_ts is not None:
                    stmt = stmt.where(Notification.created_at > cursor_ts)
                stmt = stmt.order_by(Notification.created_at.asc(), Notification.id.asc()).limit(30)
                rows = list(db.scalars(stmt))
                for row in rows:
                    payload = _serialize(row)
                    yield f"event: notification\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    cursor_ts = row.created_at
                    cursor_id = row.id
                    idle_ticks = 0
            finally:
                db.close()

            idle_ticks += 1
            if idle_ticks % 3 == 0:
                yield ": keepalive\n\n"
            await asyncio.sleep(2.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
