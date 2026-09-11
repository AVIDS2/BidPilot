from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db
from contracts import MemoryScope

from .schemas import (
    MemoryCompilationCreate,
    MemoryCompilationRead,
    MemoryContextRead,
    MemoryContextRequest,
    MemoryCreate,
    MemoryEvidenceMapRead,
    MemoryGraphExtractionCreate,
    MemoryGraphExtractionRead,
    MemoryGraphReviewDecisionCreate,
    MemoryGraphReviewDecisionRead,
    MemoryPortfolioProjectRead,
    MemoryReject,
    MemorySupersedeCreate,
    MemoryUpdate,
    PersonalMemoryClearRead,
    PersonalMemoryRead,
    MemoryRead,
)
from .service import (
    approve_memory_command,
    create_memory_command,
    delete_memory_command,
    get_memory_evidence_map_query,
    get_memory_compilation_query,
    list_memory_portfolio_query,
    list_memory_query,
    list_personal_memory_query,
    clear_personal_memory_command,
    delete_personal_profile_memory_command,
    memory_context_query,
    start_memory_compilation_command,
    start_memory_graph_extraction_command,
    review_memory_graph_item_command,
    reject_memory_command,
    supersede_memory_command,
    update_memory_command,
)


router = APIRouter(prefix="/memory", tags=["memory"])


@router.post("", response_model=MemoryRead, status_code=status.HTTP_201_CREATED)
def create_memory(
    payload: MemoryCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> MemoryRead:
    return create_memory_command(db, payload, current_user)


@router.get("", response_model=list[MemoryRead])
def list_memory(
    project_id: str | None = None,
    scope: MemoryScope | None = None,
    include_proposed: bool = False,
    include_history: bool = False,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[MemoryRead]:
    return list_memory_query(
        db,
        current_user,
        project_id=project_id,
        scope=scope,
        include_proposed=include_proposed,
        include_history=include_history,
    )


@router.get("/profile", response_model=PersonalMemoryRead)
def list_personal_memory(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> PersonalMemoryRead:
    return list_personal_memory_query(db, current_user)


@router.delete("/profile", response_model=PersonalMemoryClearRead)
def clear_personal_memory(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> PersonalMemoryClearRead:
    return clear_personal_memory_command(db, current_user)


@router.delete("/profile/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_personal_profile_memory(
    memory_id: str,
    current_user: CurrentUser = Depends(require_auth),
) -> Response:
    delete_personal_profile_memory_command(current_user, memory_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/portfolio", response_model=list[MemoryPortfolioProjectRead])
def list_memory_portfolio(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[MemoryPortfolioProjectRead]:
    return list_memory_portfolio_query(db, current_user, limit=limit)


@router.get("/evidence-map", response_model=MemoryEvidenceMapRead)
def get_memory_evidence_map(
    project_id: str,
    max_records: int = Query(default=40, ge=1, le=100),
    max_sources: int = Query(default=80, ge=1, le=160),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> MemoryEvidenceMapRead:
    return get_memory_evidence_map_query(
        db,
        current_user,
        project_id=project_id,
        max_records=max_records,
        max_sources=max_sources,
    )


@router.post("/context", response_model=MemoryContextRead)
def get_memory_context(
    payload: MemoryContextRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> MemoryContextRead:
    return memory_context_query(db, payload, current_user)


@router.post("/compile", response_model=MemoryCompilationRead, status_code=status.HTTP_201_CREATED)
def start_memory_compilation(
    payload: MemoryCompilationCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> MemoryCompilationRead:
    return start_memory_compilation_command(db, payload, current_user)


@router.post("/graph-extractions", response_model=MemoryGraphExtractionRead, status_code=status.HTTP_202_ACCEPTED)
def start_memory_graph_extraction(
    payload: MemoryGraphExtractionCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> MemoryGraphExtractionRead:
    return start_memory_graph_extraction_command(db, payload, current_user)


@router.post(
    "/{memory_id}/graph-review",
    response_model=MemoryGraphReviewDecisionRead,
)
def review_memory_graph_item(
    memory_id: str,
    payload: MemoryGraphReviewDecisionCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> MemoryGraphReviewDecisionRead:
    return review_memory_graph_item_command(db, memory_id, payload, current_user)


@router.get("/compilations/{compilation_run_id}", response_model=MemoryCompilationRead)
def get_memory_compilation(
    compilation_run_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> MemoryCompilationRead:
    return get_memory_compilation_query(db, compilation_run_id, current_user)


@router.post("/{memory_id}/approve", response_model=MemoryRead)
def approve_memory(
    memory_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> MemoryRead:
    return approve_memory_command(db, memory_id, current_user)


@router.patch("/{memory_id}", response_model=MemoryRead)
def update_memory(
    memory_id: str,
    payload: MemoryUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> MemoryRead:
    return update_memory_command(db, memory_id, payload, current_user)


@router.post("/{memory_id}/reject", response_model=MemoryRead)
def reject_memory(
    memory_id: str,
    payload: MemoryReject,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> MemoryRead:
    return reject_memory_command(db, memory_id, payload, current_user)


@router.post("/{memory_id}/supersede", response_model=MemoryRead)
def supersede_memory(
    memory_id: str,
    payload: MemorySupersedeCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> MemoryRead:
    return supersede_memory_command(db, memory_id, payload, current_user)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> Response:
    delete_memory_command(db, memory_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
