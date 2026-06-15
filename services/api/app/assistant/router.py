"""Assistant API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .schemas import AssistantRequest
from .service import stream_assistant_response

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/stream")
async def assistant_stream(
    payload: AssistantRequest,
    user: CurrentUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    return StreamingResponse(
        stream_assistant_response(db, user, payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
