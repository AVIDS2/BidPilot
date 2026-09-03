from fastapi import APIRouter, Depends, HTTPException, status
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.access.service import require_execution_run_capability
from app.auth.service import require_auth, require_stream_auth
from app.db import get_db
from app.usage.service import UsageLimitExceeded

from .schemas import (
    DraftSectionRequest,
    DraftSectionResponse,
    RedraftSectionRequest,
    ResumeRunRequest,
)
from .service import draft_section_command, redraft_section_command, resume_run_command
from .streaming import stream_graph_events

router = APIRouter(prefix="/drafting", tags=["drafting"])


@router.post("/sections", response_model=DraftSectionResponse, status_code=status.HTTP_202_ACCEPTED)
def draft_section(
    payload: DraftSectionRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> DraftSectionResponse:
    try:
        return draft_section_command(db, payload, current_user)
    except UsageLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.post("/sections/redraft", response_model=DraftSectionResponse, status_code=status.HTTP_202_ACCEPTED)
def redraft_section(
    payload: RedraftSectionRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> DraftSectionResponse:
    try:
        return redraft_section_command(db, payload, current_user)
    except UsageLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.post("/runs/{run_id}/resume", response_model=DraftSectionResponse)
def resume_run(
    run_id: str,
    payload: ResumeRunRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> DraftSectionResponse:
    """Resume an interrupted drafting run after human review.

    The LangGraph graph pauses at the ``human_approval`` node when the
    quality review passes.  This endpoint accepts the human decision
    (approve or reject with feedback) and resumes graph execution.

    Returns 404 if the run does not exist, or 409 if the run is not in
    a resumable state.
    """
    try:
        return resume_run_command(db, run_id, payload, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/runs/{run_id}/stream")
async def stream_run_events(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_stream_auth),
):
    """SSE endpoint for real-time graph execution progress.

    Emits Server-Sent Events as the LangGraph agent graph progresses
    through its nodes.  Clients can consume this with
    ``EventSource`` in the browser or any SSE client.

    Event types:

    - ``connected``: initial connection with run metadata
    - ``node_started``: a graph node has begun executing
    - ``node_completed``: a graph node finished with a result summary
    - ``review_result``: quality review output (passed, issues, score)
    - ``human_approval_required``: graph paused for HITL review
    - ``graph_completed``: graph finished successfully
    - ``graph_error``: an error occurred during execution
    - ``heartbeat``: periodic status update (fallback mode only)

    The stream automatically terminates when the run reaches a terminal
    status (succeeded, failed, cancelled, error) or after 5 minutes.
    """
    require_execution_run_capability(
        db,
        current_user=current_user,
        run_id=run_id,
        capability="project.read",
    )
    # The stream generator opens short read sessions per poll. Release the
    # request dependency's transaction before returning the long-lived SSE.
    db.rollback()
    return EventSourceResponse(stream_graph_events(run_id, db))
