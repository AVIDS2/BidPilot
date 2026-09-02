"""Read-only runtime run and event replay endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db
from app.models import RuntimeAction, RuntimeApproval, RuntimeRun

from .events import list_events_after
from .repository import get_visible_runtime_run
from .schemas import (
    RuntimeActionResolutionRead,
    RuntimeApprovalResolveRequest,
    RuntimeChildRunRead,
    RuntimeEventRead,
    RuntimeEventsResponse,
    RuntimeLinkedWorkflowRun,
    RuntimeRunListItem,
    RuntimeRunRead,
)
from .service import (
    RuntimeApprovalExpiredError,
    RuntimeApprovalResolvedError,
    finalize_requested_runtime_cancellation,
    list_linked_workflow_runs,
    list_runtime_child_runs,
    list_runtime_runs_query,
    request_runtime_cancellation,
    resolve_approval,
)
from .pi_control import cancel_active_pi_execution, request_pi_abort


router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get("/runs", response_model=list[RuntimeRunListItem])
def list_runtime_runs(
    limit: int = Query(default=50, ge=1, le=100),
    conversation_id: str | None = Query(default=None),
    kind: list[str] | None = Query(default=None),
    live_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[RuntimeRunListItem]:
    return [
        RuntimeRunListItem(
            id=row.run.id,
            kind=row.run.kind,
            status=row.run.status,
            project_id=row.run.project_id,
            conversation_id=row.run.conversation_id,
            project_name=row.project_name,
            engine=row.run.engine,
            created_at=row.run.created_at,
            started_at=row.run.started_at,
            finished_at=row.run.finished_at,
            latest_event_summary=row.latest_event_summary,
        )
        for row in list_runtime_runs_query(
            db,
            current_user,
            limit=limit,
            conversation_id=conversation_id,
            kinds=kind,
            live_only=live_only,
        )
    ]


@router.get("/runs/{run_id}", response_model=RuntimeRunRead)
def get_runtime_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> RuntimeRunRead:
    run = get_visible_runtime_run(db, run_id, current_user)
    linked_workflow_runs = list_linked_workflow_runs(
        db,
        current_user,
        parent_run_id=run.id,
    )
    return RuntimeRunRead(
        id=run.id,
        kind=run.kind,
        status=run.status,
        project_id=run.project_id,
        conversation_id=run.conversation_id,
        execution_run_id=run.execution_run_id,
        engine=run.engine,
        trace_id=run.trace_id,
        parent_run_id=run.parent_run_id,
        linked_workflow_runs=[
            RuntimeLinkedWorkflowRun(
                id=child.id,
                status=child.status,
                project_id=child.project_id,
                execution_run_id=child.execution_run_id,
                engine=child.engine,
                created_at=child.created_at,
                started_at=child.started_at,
                finished_at=child.finished_at,
            )
            for child in linked_workflow_runs
        ],
    )


@router.get("/runs/{run_id}/children", response_model=list[RuntimeChildRunRead])
def list_runtime_children(
    run_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[RuntimeChildRunRead]:
    children = list_runtime_child_runs(
        db,
        current_user,
        parent_run_id=run_id,
        limit=limit,
    )
    items: list[RuntimeChildRunRead] = []
    for row in children:
        subagent = (row.run.input_json or {}).get("subagent")
        safe_subagent = subagent if isinstance(subagent, dict) else {}
        items.append(RuntimeChildRunRead(
            id=row.run.id,
            parent_run_id=run_id,
            kind=row.run.kind,
            status=row.run.status,
            profile=(str(safe_subagent.get("profile")) if safe_subagent.get("profile") else None),
            mode=(str(safe_subagent.get("mode")) if safe_subagent.get("mode") else None),
            created_at=row.run.created_at,
            started_at=row.run.started_at,
            finished_at=row.run.finished_at,
            latest_event_summary=row.latest_event_summary,
        ))
    return items


@router.get("/runs/{run_id}/events", response_model=RuntimeEventsResponse)
def replay_runtime_events(
    run_id: str,
    after_sequence: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> RuntimeEventsResponse:
    get_visible_runtime_run(db, run_id, current_user)
    events = list_events_after(db, run_id, after_sequence=after_sequence)
    return RuntimeEventsResponse(
        items=[
            RuntimeEventRead(
                event_id=event.id,
                run_id=event.run_id,
                parent_event_id=event.parent_event_id,
                sequence=event.sequence,
                type=event.event_type,
                public_summary=event.public_summary,
                payload=event.payload_json or {},
                schema_version=event.schema_version,
                timestamp=event.created_at,
            )
            for event in events
        ]
    )


@router.post("/runs/{run_id}/cancel", response_model=RuntimeRunRead)
async def cancel_runtime_run_request(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> RuntimeRunRead:
    try:
        run = request_runtime_cancellation(db, current_user, run_id=run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if run.kind == "assistant_turn" and run.status == "cancel_requested":
        await request_pi_abort(run.id)
        cancel_active_pi_execution(run.id)
        # The durable cancellation is the user-visible boundary. The sidecar
        # has received the official abort request when it is reachable, and a
        # same-process API execution is interrupted as well. Either way, a
        # late provider response cannot publish success over this terminal
        # state, while the Pi session can finish its own cleanup in the
        # background.
        run = finalize_requested_runtime_cancellation(db, run.id)
    return RuntimeRunRead(
        id=run.id,
        kind=run.kind,
        status=run.status,
        project_id=run.project_id,
        conversation_id=run.conversation_id,
        execution_run_id=run.execution_run_id,
        engine=run.engine,
        trace_id=run.trace_id,
        parent_run_id=run.parent_run_id,
    )


@router.post("/approvals/{approval_id}/resolve", response_model=RuntimeActionResolutionRead)
def resolve_runtime_approval(
    approval_id: str,
    payload: RuntimeApprovalResolveRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> RuntimeActionResolutionRead:
    approval = db.get(RuntimeApproval, approval_id)
    if approval is not None and approval.user_id == current_user.id and approval.org_id == current_user.org_id:
        action = db.get(RuntimeAction, approval.action_id)
        run = db.get(RuntimeRun, action.run_id) if action is not None else None
        if run is not None and run.engine == "langgraph_operator":
            raise HTTPException(
                status_code=409,
                detail="This approval must be resumed through the assistant runtime.",
            )
    try:
        result = resolve_approval(
            db,
            current_user,
            approval_id=approval_id,
            decision=payload.decision,
            edited_arguments=payload.edited_arguments,
        )
    except (RuntimeApprovalExpiredError, RuntimeApprovalResolvedError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RuntimeActionResolutionRead(
        action_id=result.action.id,
        status=result.action.status,
        public_summary=result.action.public_summary,
        approval_status=result.approval.status if result.approval is not None else None,
    )
