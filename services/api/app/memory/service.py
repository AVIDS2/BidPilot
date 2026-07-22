from __future__ import annotations

import hashlib
import logging
import os
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access.service import require_bundle_capability, require_project_capability
from app.auth.schemas import CurrentUser
from app.audit.service import record_audit_event
from app.celery_client import celery
from app.outbox.service import enqueue_workflow_task, request_task_outbox_dispatch
from app.runtime.service import create_workflow_bridge_run
from app.models import (
    AuditEvent,
    Bundle,
    ChatConversation,
    ChatMessage,
    Evidence,
    ExecutionRun,
    KnowledgeChunk,
    MemoryCompilationRun,
    MemoryEvent,
    MemoryEvidenceLink,
    MemoryGraphReviewDecision,
    MemoryRecord,
    ProviderConfig,
    RequirementItem,
    SourceDocument,
    TaskOutboxEvent,
)
from app.usage.schemas import ProviderSource
from app.usage.service import (
    EMBEDDING_INDEX_STARTED,
    WORKFLOW_DRAFT_STARTED,
    UsageLimitExceeded,
    attach_model_usage_reservation,
    check_indexing_quota,
    check_workflow_quota,
    record_usage_event,
    reserve_workflow_model_tokens,
)
from contracts import (
    MemoryCitation,
    MemoryCitationSource,
    MemoryGraphProposal,
    MemoryKind,
    MemoryProposal,
    MemoryProposalOrigin,
    MemoryScope,
    MemoryStatus,
    memory_graph_item_id,
    memory_graph_proposal_fingerprint,
    memory_graph_source_snapshot_fingerprint,
)
from contracts.memory_service import build_memory_context_pack
from contracts.memory_repository import has_visible_memory
from contracts.retrieval import normalize_retrieval_text

from .repository import (
    get_memory_record,
    list_memory_portfolio_rows,
    list_memory_records,
    list_project_evidence_map_rows,
)
from .schemas import (
    MemoryCompilationCreate,
    MemoryCompilationRead,
    MemoryContextRead,
    MemoryContextRequest,
    MemoryCreate,
    MemoryEvidenceMapEdgeRead,
    MemoryEvidenceMapNodeRead,
    MemoryEvidenceMapRead,
    MemoryGraphEntityRead,
    MemoryGraphExtractionCreate,
    MemoryGraphExtractionRead,
    MemoryGraphProposalRead,
    MemoryGraphRelationRead,
    MemoryGraphReviewDecisionCreate,
    MemoryGraphReviewDecisionRead,
    MemoryPortfolioProjectRead,
    MemoryRead,
)

logger = logging.getLogger(__name__)

_DEFAULT_AGENT_MEMORY_EMBEDDING_TIMEOUT_SECONDS = 2.5


def create_memory_command(db: Session, payload: MemoryCreate, current_user: CurrentUser) -> MemoryRead:
    org_id = _org_id(current_user)
    _require_create_scope_access(db, current_user, payload)
    citations = _canonicalize_client_citations(
        db,
        current_user=current_user,
        project_id=payload.project_id,
        citations=tuple(payload.citations),
    )
    _validate_memory_graph_proposal(payload, citations)
    proposal = MemoryProposal(
        org_id=org_id,
        project_id=payload.project_id,
        owner_user_id=current_user.id if payload.scope is MemoryScope.USER_PRIVATE else None,
        scope=payload.scope,
        kind=payload.kind,
        title=payload.title,
        body_markdown=payload.body_markdown,
        structured_data_json=payload.structured_data_json,
        origin=MemoryProposalOrigin.USER,
        evidence_ids=tuple(citation.source_id for citation in citations),
        expires_at=payload.expires_at,
    )
    status = MemoryStatus.ACTIVE if proposal.scope is MemoryScope.USER_PRIVATE else MemoryStatus.PROPOSED
    record = MemoryRecord(
        org_id=proposal.org_id,
        project_id=proposal.project_id,
        owner_user_id=proposal.owner_user_id,
        scope=proposal.scope.value,
        kind=proposal.kind.value,
        status=status.value,
        title=proposal.title,
        body_markdown=proposal.body_markdown,
        structured_data_json=proposal.structured_data_json,
        retrieval_text=normalize_retrieval_text(f"{proposal.title}\n{proposal.body_markdown}"),
        embedding_status="pending",
        origin=proposal.origin.value,
        created_by_actor_type="user",
        created_by_actor_id=current_user.id,
        expires_at=proposal.expires_at,
    )
    db.add(record)
    db.flush()
    for citation in citations:
        db.add(_citation_link(record.id, citation))
    _record_event(db, record, current_user, "memory.created", {"status": status.value})
    db.commit()
    db.refresh(record)
    if status is MemoryStatus.ACTIVE:
        _request_memory_embedding_index(db, record, current_user)
    return _to_read(record)


def approve_memory_command(db: Session, memory_id: str, current_user: CurrentUser) -> MemoryRead:
    record = _require_record_for_project_action(db, memory_id, current_user, capability="memory.approve")
    if record.status != MemoryStatus.PROPOSED.value:
        raise HTTPException(status_code=409, detail="Only proposed memory can be approved")
    graph_proposal = _memory_graph_proposal_for_record(record)
    structured_data = record.structured_data_json or {}
    if "memory_graph_proposal" in structured_data and graph_proposal is None:
        raise HTTPException(status_code=409, detail="Graph proposal is invalid; regenerate it before approval")
    if graph_proposal is not None:
        pending_items = _graph_proposal_pending_item_count(record, graph_proposal)
        if pending_items:
            raise HTTPException(
                status_code=409,
                detail="Review every entity and relation in the graph proposal before approving it",
            )
        _ensure_graph_proposal_source_current(db, record)
    record.status = MemoryStatus.ACTIVE.value
    _record_event(db, record, current_user, "memory.approved", None)
    db.commit()
    db.refresh(record)
    _request_memory_embedding_index(db, record, current_user)
    return _to_read(record)


def review_memory_graph_item_command(
    db: Session,
    memory_id: str,
    payload: MemoryGraphReviewDecisionCreate,
    current_user: CurrentUser,
) -> MemoryGraphReviewDecisionRead:
    """Record one fingerprint-bound, project-authorized graph review decision."""
    record = _require_record_for_project_action(db, memory_id, current_user, capability="memory.approve")
    if record.status != MemoryStatus.PROPOSED.value:
        raise HTTPException(status_code=409, detail="Only proposed graph items can be reviewed")
    proposal = _memory_graph_proposal_for_record(record)
    if proposal is None:
        raise HTTPException(status_code=409, detail="Memory record has no graph proposal")
    try:
        proposal.validate_evidence_sources(
            {(link.source_type, link.source_id) for link in record.evidence_links}
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail="Graph proposal evidence is no longer valid; regenerate it",
        ) from exc

    proposal_fingerprint = _graph_proposal_fingerprint(proposal)
    item_type = _graph_item_type_for_id(proposal, proposal_fingerprint, payload.item_id)
    if item_type is None:
        raise HTTPException(status_code=404, detail="Graph proposal item not found")

    decision = db.scalar(
        select(MemoryGraphReviewDecision)
        .where(
            MemoryGraphReviewDecision.proposal_memory_record_id == record.id,
            MemoryGraphReviewDecision.item_id == payload.item_id,
        )
        .with_for_update()
    )
    if decision is None:
        decision = MemoryGraphReviewDecision(
            org_id=record.org_id,
            project_id=record.project_id,
            proposal_memory_record_id=record.id,
            item_id=payload.item_id,
            item_type=item_type,
            proposal_fingerprint=proposal_fingerprint,
            decision=payload.decision,
            decision_note=payload.decision_note,
            reviewer_user_id=current_user.id,
        )
        db.add(decision)
    else:
        if decision.proposal_fingerprint != proposal_fingerprint or decision.item_type != item_type:
            raise HTTPException(status_code=409, detail="Graph proposal changed; review it again")
        decision.decision = payload.decision
        decision.decision_note = payload.decision_note
        decision.reviewer_user_id = current_user.id
        decision.reviewed_at = _utc_naive_now()

    db.add(
        MemoryEvent(
            memory_record_id=record.id,
            org_id=record.org_id,
            project_id=record.project_id,
            actor_type="user",
            actor_id=current_user.id,
            event_type="memory.graph_item_reviewed",
            payload_json={
                "item_id": payload.item_id,
                "item_type": item_type,
                "decision": payload.decision,
            },
        )
    )
    record_audit_event(
        db,
        project_id=record.project_id,
        event_type="memory.graph_item_reviewed",
        actor_type="user",
        actor_id=current_user.id,
        payload={"memory_record_id": record.id, "item_id": payload.item_id, "decision": payload.decision},
    )
    db.commit()
    db.refresh(decision)
    return MemoryGraphReviewDecisionRead(
        item_id=decision.item_id,
        item_type=decision.item_type,
        decision=decision.decision,
        decision_note=decision.decision_note,
        reviewed_at=decision.reviewed_at,
    )


def delete_memory_command(db: Session, memory_id: str, current_user: CurrentUser) -> None:
    record = get_memory_record(db, memory_id)
    if record is None or record.org_id != _org_id(current_user):
        raise HTTPException(status_code=404, detail="Memory record not found")
    if record.scope == MemoryScope.USER_PRIVATE.value:
        if record.owner_user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Memory record not found")
    elif record.project_id:
        if record.created_by_actor_id == current_user.id and record.status == MemoryStatus.PROPOSED.value:
            require_project_capability(
                db,
                current_user=current_user,
                project_id=record.project_id,
                capability="memory.propose",
            )
        else:
            require_project_capability(
                db,
                current_user=current_user,
                project_id=record.project_id,
                capability="memory.approve",
            )
    else:
        raise HTTPException(status_code=403, detail="Organization memory deletion is not enabled")

    record.status = MemoryStatus.DELETED.value
    record.deleted_at = _utc_naive_now()
    record.embedding = None
    record.embedding_profile = None
    record.embedding_status = "deleted"
    record.embedding_error_code = None
    _record_event(db, record, current_user, "memory.deleted", None)
    db.commit()


def list_memory_query(
    db: Session,
    current_user: CurrentUser,
    *,
    project_id: str | None,
    scope: MemoryScope | None,
    include_proposed: bool,
) -> list[MemoryRead]:
    org_id = _org_id(current_user)
    if project_id:
        require_project_capability(db, current_user=current_user, project_id=project_id, capability="memory.read")
        if scope is MemoryScope.USER_PRIVATE:
            records = list_memory_records(
                db,
                org_id=org_id,
                project_id=project_id,
                owner_user_id=current_user.id,
                scope=MemoryScope.USER_PRIVATE.value,
                include_proposed=False,
            )
            return [_to_read(record) for record in records]
        if include_proposed:
            require_project_capability(db, current_user=current_user, project_id=project_id, capability="memory.approve")
        shared_records = list_memory_records(
            db,
            org_id=org_id,
            project_id=project_id,
            owner_user_id=None,
            scope=scope.value if scope is not None else MemoryScope.PROJECT_SHARED.value,
            include_proposed=include_proposed,
        )
        if scope is not None:
            return [_to_read(record) for record in shared_records]

        # A project Wiki can include the caller's own project preferences, but
        # never another member's private record. Keep this as a separate query
        # so private data is not even enumerated in the shared query path.
        private_records = list_memory_records(
            db,
            org_id=org_id,
            project_id=project_id,
            owner_user_id=current_user.id,
            scope=MemoryScope.USER_PRIVATE.value,
            include_proposed=False,
        )
        records = [*shared_records, *private_records]
        records.sort(key=lambda record: (record.updated_at or datetime.min, record.id), reverse=True)
        return [_to_read(record) for record in records]

    if scope not in {None, MemoryScope.USER_PRIVATE}:
        raise HTTPException(status_code=400, detail="project_id is required for shared memory")
    records = list_memory_records(
        db,
        org_id=org_id,
        project_id=None,
        owner_user_id=current_user.id,
        scope=MemoryScope.USER_PRIVATE.value,
        include_proposed=False,
    )
    # Project-scoped private memory may carry project source locators. Do not
    # return it outside an authorized project request, even to its owner.
    return [
        _to_read(record)
        for record in records
        if record.project_id is None
    ]


def list_memory_portfolio_query(
    db: Session,
    current_user: CurrentUser,
    *,
    limit: int = 50,
) -> list[MemoryPortfolioProjectRead]:
    safe_limit = min(max(limit, 1), 100)
    return [
        MemoryPortfolioProjectRead(
            project_id=row.project_id,
            project_name=row.project_name,
            active_shared_count=row.active_shared_count,
            proposed_shared_count=row.proposed_shared_count,
            latest_shared_memory_at=row.latest_shared_memory_at,
            latest_compilation_status=row.latest_compilation_status,
            latest_compilation_at=row.latest_compilation_at,
        )
        for row in list_memory_portfolio_rows(
            db,
            current_user=current_user,
            limit=safe_limit,
        )
    ]


def get_memory_evidence_map_query(
    db: Session,
    current_user: CurrentUser,
    *,
    project_id: str,
    max_records: int = 40,
    max_sources: int = 80,
) -> MemoryEvidenceMapRead:
    """Build a small, project-authorized provenance map for the Knowledge UI.

    This is intentionally separate from memory-context retrieval: it never
    returns record bodies, raw source identifiers, or a cross-project subgraph.
    """
    require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="memory.read",
    )
    safe_max_records = min(max(max_records, 1), 100)
    safe_max_sources = min(max(max_sources, 1), 160)
    rows = list_project_evidence_map_rows(
        db,
        org_id=_org_id(current_user),
        project_id=project_id,
        max_records=safe_max_records,
    )

    nodes = [
        MemoryEvidenceMapNodeRead(
            id=f"memory:{record.id}",
            node_type="memory",
            label=record.title,
            memory_kind=record.kind,
        )
        for record in rows.records
    ]
    memory_node_ids = {record.id: f"memory:{record.id}" for record in rows.records}
    source_nodes: dict[tuple[str, str], MemoryEvidenceMapNodeRead] = {}
    source_node_ids: dict[tuple[str, str], str] = {}
    edges: list[MemoryEvidenceMapEdgeRead] = []
    truncated = rows.truncated

    for citation in rows.citations:
        source_key = (citation.source_type, citation.source_id)
        if source_key not in source_nodes:
            if len(source_nodes) >= safe_max_sources:
                truncated = True
                continue
            source_node_id = _evidence_map_source_node_id(*source_key)
            source_node_ids[source_key] = source_node_id
            source_nodes[source_key] = MemoryEvidenceMapNodeRead(
                id=source_node_id,
                node_type="source",
                label=citation.label,
                source_type=citation.source_type,
            )
        source_node_id = source_node_ids[source_key]
        memory_node_id = memory_node_ids.get(citation.memory_record_id)
        if memory_node_id is None:
            continue
        edges.append(
            MemoryEvidenceMapEdgeRead(
                id=f"edge:{citation.memory_record_id}:{source_node_id}",
                source=memory_node_id,
                target=source_node_id,
                predicate="cites",
            )
        )

    return MemoryEvidenceMapRead(
        project_id=project_id,
        nodes=tuple([*nodes, *source_nodes.values()]),
        edges=tuple(edges),
        truncated=truncated,
    )


def memory_context_query(
    db: Session,
    payload: MemoryContextRequest,
    current_user: CurrentUser,
) -> MemoryContextRead:
    """Authorize a requested project before the optional embedding provider call."""
    _authorize_memory_context(db, current_user=current_user, project_id=payload.project_id)
    return _memory_context_for_user(
        db,
        current_user=current_user,
        project_id=payload.project_id,
        query=payload.query,
        top_k=payload.top_k,
        max_characters=payload.max_characters,
    )


def memory_context_for_agent(
    db: Session,
    *,
    current_user: CurrentUser,
    project_id: str | None,
    query: str,
    top_k: int = 8,
    max_characters: int = 12_000,
) -> MemoryContextRead:
    """Internal Agent entry point that preserves the same authorization boundary."""
    _authorize_memory_context(db, current_user=current_user, project_id=project_id)
    return _memory_context_for_user(
        db,
        current_user=current_user,
        project_id=project_id,
        query=query,
        top_k=top_k,
        max_characters=max_characters,
        embedding_timeout_seconds=_agent_memory_embedding_timeout_seconds(),
    )


def start_memory_compilation_command(
    db: Session,
    payload: MemoryCompilationCreate,
    current_user: CurrentUser,
) -> MemoryCompilationRead:
    """Queue a reviewable, deterministic Bid Wiki compilation for one project."""
    access = require_project_capability(
        db,
        current_user=current_user,
        project_id=payload.project_id,
        capability="memory.approve",
    )
    bundle: Bundle | None = None
    if payload.bundle_id:
        bundle = require_bundle_capability(
            db,
            current_user=current_user,
            bundle_id=payload.bundle_id,
            capability="memory.approve",
        )
        if bundle.project_id != access.project.id:
            raise HTTPException(status_code=404, detail="Bundle not found")

    source_stmt = (
        select(SourceDocument.id)
        .join(Bundle, Bundle.id == SourceDocument.bundle_id)
        .where(
            Bundle.project_id == access.project.id,
            SourceDocument.parse_status == "parsed",
        )
        .order_by(SourceDocument.id.asc())
    )
    if bundle is not None:
        source_stmt = source_stmt.where(Bundle.id == bundle.id)
    source_ids = list(db.scalars(source_stmt).all())
    if not source_ids:
        raise HTTPException(status_code=409, detail="No parsed source material is ready for Bid Wiki compilation")

    run = MemoryCompilationRun(
        org_id=_org_id(current_user),
        project_id=access.project.id,
        bundle_id=bundle.id if bundle is not None else None,
        initiated_by_user_id=current_user.id,
        status="queued",
        input_source_ids_json=source_ids,
        input_memory_ids_json=[],
        policy_version="memory-compiler-v1",
    )
    db.add(run)
    db.flush()
    record_audit_event(
        db,
        project_id=access.project.id,
        event_type="memory.compilation_requested",
        actor_type="user",
        actor_id=current_user.id,
        payload={"compilation_run_id": run.id, "bundle_id": run.bundle_id, "source_count": len(source_ids)},
    )
    db.commit()
    db.refresh(run)
    try:
        celery.send_task("worker.compile_bid_wiki", args=[run.id])
    except Exception as exc:
        run.status = "dispatch_failed"
        run.error_code = "task_dispatch_failed"
        db.commit()
        raise HTTPException(status_code=503, detail="Bid Wiki compilation could not be queued") from exc
    return _to_compilation_read(run)


_MEMORY_GRAPH_PROPOSER_POLICY_VERSION = "memory-graph-proposer-v1"
_MEMORY_GRAPH_RETRYABLE_RUN_STATUSES = frozenset({"failed", "dispatch_failed", "cancelled"})


def start_memory_graph_extraction_command(
    db: Session,
    payload: MemoryGraphExtractionCreate,
    current_user: CurrentUser,
) -> MemoryGraphExtractionRead:
    """Queue one billable, reviewable graph proposal from approved shared memory.

    The job is a normal governed workflow: project authorization, model quota,
    durable outbox delivery, runtime events, and usage accounting all apply.
    It can only create a *proposed* entity-note record; it never materializes
    graph rows or bypasses the existing human approval boundary.
    """
    access = require_project_capability(
        db,
        current_user=current_user,
        project_id=payload.project_id,
        capability="memory.approve",
    )
    require_project_capability(
        db,
        current_user=current_user,
        project_id=access.project.id,
        capability="workflow.run",
    )
    source_record = get_memory_record(db, payload.memory_record_id)
    if (
        source_record is None
        or source_record.org_id != _org_id(current_user)
        or source_record.project_id != access.project.id
        or source_record.scope != MemoryScope.PROJECT_SHARED.value
        or source_record.status != MemoryStatus.ACTIVE.value
        or source_record.deleted_at is not None
        or (source_record.expires_at is not None and source_record.expires_at <= _utc_naive_now())
    ):
        raise HTTPException(status_code=404, detail="Active shared memory record not found")

    evidence_links = list(
        db.scalars(
            select(MemoryEvidenceLink)
            .where(MemoryEvidenceLink.memory_record_id == source_record.id)
            .order_by(MemoryEvidenceLink.id.asc())
        ).all()
    )
    if not evidence_links:
        raise HTTPException(status_code=409, detail="Memory record has no evidence for graph extraction")
    snapshot_fingerprint = _memory_graph_snapshot_fingerprint(source_record, evidence_links)
    duplicate = db.scalar(
        select(MemoryRecord.id)
        .where(
            MemoryRecord.org_id == _org_id(current_user),
            MemoryRecord.project_id == access.project.id,
            MemoryRecord.content_fingerprint == snapshot_fingerprint,
            MemoryRecord.kind == MemoryKind.ENTITY_NOTE.value,
            MemoryRecord.status.in_((MemoryStatus.PROPOSED.value, MemoryStatus.ACTIVE.value)),
            MemoryRecord.deleted_at.is_(None),
        )
        .limit(1)
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="A current graph proposal already exists for this memory record")

    deduplication_key = _memory_graph_task_deduplication_key(
        project_id=access.project.id,
        memory_record_id=source_record.id,
        snapshot_fingerprint=snapshot_fingerprint,
    )
    run = ExecutionRun(
        project_id=access.project.id,
        run_type="memory_graph_extraction",
        input_json={
            "memory_record_id": source_record.id,
            "source_snapshot_fingerprint": snapshot_fingerprint,
            "graph_policy_version": _MEMORY_GRAPH_PROPOSER_POLICY_VERSION,
        },
    )
    # Materialize a parent transaction before the Outbox savepoint. SQLite
    # otherwise treats a released savepoint as a commit, unlike PostgreSQL.
    db.add(run)
    db.flush()
    outbox_event = enqueue_workflow_task(
        db,
        org_id=current_user.org_id,
        project_id=access.project.id,
        execution_run_id=run.id,
        runtime_run_id=None,
        task_name="worker.extract_memory_graph",
        args=[],
        kwargs={},
        deduplication_key=deduplication_key,
    )
    if outbox_event.execution_run_id != run.id:
        # A competing request won the unique Outbox key. Remove this unstaged
        # candidate run before reading the winner's durable control-plane row.
        db.rollback()
        outbox_event = _memory_graph_outbox_event_for_update(
            db,
            org_id=current_user.org_id,
            deduplication_key=deduplication_key,
        )
        if outbox_event is None:
            raise HTTPException(status_code=409, detail="Graph extraction task is being initialized; retry shortly")
        existing_run = db.get(ExecutionRun, outbox_event.execution_run_id) if outbox_event.execution_run_id else None
        if existing_run is None or outbox_event.runtime_run_id is None:
            raise HTTPException(status_code=409, detail="Existing graph extraction task is incomplete; retry shortly")
        if existing_run.status not in _MEMORY_GRAPH_RETRYABLE_RUN_STATUSES or outbox_event.status != "failed":
            return _to_memory_graph_extraction_read(
                run=existing_run,
                runtime_run_id=outbox_event.runtime_run_id,
                project_id=access.project.id,
                memory_record_id=source_record.id,
                reused=True,
            )
        run = ExecutionRun(
            project_id=access.project.id,
            parent_execution_run_id=existing_run.id,
            attempt_number=existing_run.attempt_number + 1,
            run_type="memory_graph_extraction",
            input_json={
                "memory_record_id": source_record.id,
                "source_snapshot_fingerprint": snapshot_fingerprint,
                "graph_policy_version": _MEMORY_GRAPH_PROPOSER_POLICY_VERSION,
            },
        )
        db.add(run)
        db.flush()

    provider_config_id = _memory_graph_provider_config_id_for_user(db, current_user, payload.provider_config_id)
    provider_source = ProviderSource.BYOK if provider_config_id else ProviderSource.OFFICIAL
    provider_type = _memory_graph_provider_type(db, provider_config_id)
    check_workflow_quota(db, current_user.id, current_user.org_id, provider_source)
    reservation_key = f"memory-graph:{uuid4()}"
    reservation = reserve_workflow_model_tokens(
        db,
        user_id=current_user.id,
        org_id=current_user.org_id,
        provider_source=provider_source,
        provider_type=provider_type,
        reservation_key=reservation_key,
        project_id=access.project.id,
    )
    try:
        runtime_run = create_workflow_bridge_run(
            db,
            current_user,
            execution_run_id=run.id,
            project_id=access.project.id,
            provider_config_id=provider_config_id,
            reasoning_effort=payload.reasoning_effort,
            engine="memory_graph_extraction",
            commit=False,
        )
    except Exception:
        db.rollback()
        raise
    attach_model_usage_reservation(
        db,
        reservation,
        execution_run_id=run.id,
        runtime_run_id=runtime_run.id,
    )
    run.input_json = {
        **(run.input_json or {}),
        "runtime_run_id": runtime_run.id,
        "model_usage_reservation_key": reservation_key,
    }
    record_usage_event(
        db,
        user_id=current_user.id,
        org_id=current_user.org_id,
        project_id=access.project.id,
        event_type=WORKFLOW_DRAFT_STARTED,
        provider_source=provider_source,
        execution_run_id=run.id,
    )
    task_kwargs: dict[str, object] = {"runtime_run_id": runtime_run.id}
    if provider_config_id:
        task_kwargs["provider_config_id"] = provider_config_id
    if payload.reasoning_effort:
        task_kwargs["reasoning_effort"] = payload.reasoning_effort
    outbox_event.execution_run_id = run.id
    outbox_event.runtime_run_id = runtime_run.id
    outbox_event.args_json = [run.id, access.project.id, source_record.id]
    outbox_event.kwargs_json = task_kwargs
    outbox_event.status = "pending"
    outbox_event.available_at = _utc_naive_now()
    outbox_event.lease_expires_at = None
    outbox_event.last_error_code = None
    outbox_event.dispatched_at = None
    outbox_event.completed_at = None
    record_audit_event(
        db,
        project_id=access.project.id,
        event_type="memory.graph_extraction_requested",
        actor_type="user",
        actor_id=current_user.id,
        payload={"execution_run_id": run.id, "source_memory_record_id": source_record.id},
    )
    db.commit()
    request_task_outbox_dispatch(outbox_event.id)
    return _to_memory_graph_extraction_read(
        run=run,
        runtime_run_id=runtime_run.id,
        project_id=access.project.id,
        memory_record_id=source_record.id,
    )


def get_memory_compilation_query(
    db: Session,
    compilation_run_id: str,
    current_user: CurrentUser,
) -> MemoryCompilationRead:
    run = db.get(MemoryCompilationRun, compilation_run_id)
    if run is None or run.org_id != _org_id(current_user):
        raise HTTPException(status_code=404, detail="Memory compilation not found")
    require_project_capability(
        db,
        current_user=current_user,
        project_id=run.project_id,
        capability="memory.read",
    )
    return _to_compilation_read(run)


def _memory_context_for_user(
    db: Session,
    *,
    current_user: CurrentUser,
    project_id: str | None,
    query: str,
    top_k: int,
    max_characters: int,
    embedding_timeout_seconds: float | None = None,
) -> MemoryContextRead:
    from app.retrieval.metered_embedding import generate_metered_query_embedding

    org_id = _org_id(current_user)
    now = _utc_naive_now()
    if not has_visible_memory(
        db,
        org_id=org_id,
        user_id=current_user.id,
        project_id=project_id,
        now=now,
    ):
        pack = build_memory_context_pack(
            db,
            org_id=org_id,
            user_id=current_user.id,
            project_id=project_id,
            raw_query=query,
            profile_id=None,
            query_embedding=None,
            top_k=top_k,
            max_characters=max_characters,
        )
        return _to_memory_context_read(pack)

    embedding = generate_metered_query_embedding(
        current_user=current_user,
        project_id=project_id,
        query=query,
        workload="embedding_memory_query",
        timeout_seconds=embedding_timeout_seconds,
    )
    pack = build_memory_context_pack(
        db,
        org_id=org_id,
        user_id=current_user.id,
        project_id=project_id,
        raw_query=query,
        profile_id=embedding.profile_id if embedding.is_success else None,
        query_embedding=embedding.vector if embedding.is_success else None,
        top_k=top_k,
        max_characters=max_characters,
    )
    return _to_memory_context_read(pack)


def _authorize_memory_context(
    db: Session,
    *,
    current_user: CurrentUser,
    project_id: str | None,
) -> None:
    if project_id:
        require_project_capability(
            db,
            current_user=current_user,
            project_id=project_id,
            capability="memory.read",
        )


def _agent_memory_embedding_timeout_seconds() -> float:
    raw_value = os.environ.get("DOCPILOT_AGENT_MEMORY_EMBEDDING_TIMEOUT_SECONDS")
    try:
        value = float(raw_value) if raw_value is not None else _DEFAULT_AGENT_MEMORY_EMBEDDING_TIMEOUT_SECONDS
    except ValueError:
        value = _DEFAULT_AGENT_MEMORY_EMBEDDING_TIMEOUT_SECONDS
    return min(max(value, 0.1), 5.0)


def _evidence_map_source_node_id(source_type: str, source_id: str) -> str:
    """Keep source ids internal to this response while retaining stable edges."""
    digest = hashlib.sha256(f"{source_type}\0{source_id}".encode("utf-8")).hexdigest()[:24]
    return f"source:{digest}"


def _to_memory_context_read(pack) -> MemoryContextRead:
    return MemoryContextRead(
        project_id=pack.project_id,
        memory_version=pack.memory_version,
        items=pack.items,
        degraded_reasons=pack.degraded_reasons,
    )


def _memory_graph_provider_config_id_for_user(
    db: Session,
    current_user: CurrentUser,
    provider_config_id: str | None,
) -> str | None:
    if provider_config_id is None:
        return None
    config = db.get(ProviderConfig, provider_config_id)
    if config is None or config.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Provider config not found")
    return config.id


def _memory_graph_provider_type(db: Session, provider_config_id: str | None) -> str:
    if provider_config_id is None:
        return "openai"
    config = db.get(ProviderConfig, provider_config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Provider config not found")
    return config.provider_type


def _memory_graph_task_deduplication_key(
    *,
    project_id: str,
    memory_record_id: str,
    snapshot_fingerprint: str,
) -> str:
    return f"memory-graph:{project_id}:{memory_record_id}:{snapshot_fingerprint}"


def _memory_graph_outbox_event_for_update(
    db: Session,
    *,
    org_id: str,
    deduplication_key: str,
) -> TaskOutboxEvent | None:
    return db.scalar(
        select(TaskOutboxEvent)
        .where(
            TaskOutboxEvent.org_id == org_id,
            TaskOutboxEvent.deduplication_key == deduplication_key,
        )
        .with_for_update()
    )


def _to_memory_graph_extraction_read(
    *,
    run: ExecutionRun,
    runtime_run_id: str,
    project_id: str,
    memory_record_id: str,
    reused: bool = False,
) -> MemoryGraphExtractionRead:
    return MemoryGraphExtractionRead(
        run_id=run.id,
        runtime_run_id=runtime_run_id,
        project_id=project_id,
        memory_record_id=memory_record_id,
        status=run.status,
        reused=reused,
    )


def _memory_graph_snapshot_fingerprint(
    record: MemoryRecord,
    evidence_links: list[MemoryEvidenceLink],
) -> str:
    return memory_graph_source_snapshot_fingerprint(
        policy_version=_MEMORY_GRAPH_PROPOSER_POLICY_VERSION,
        memory_record_id=record.id,
        title=record.title,
        body_markdown=record.body_markdown,
        citations=tuple(
            MemoryCitation(
                source_type=link.source_type,
                source_id=link.source_id,
                label=link.label,
                locator_json=link.locator_json,
            )
            for link in evidence_links
        ),
    )


def _ensure_graph_proposal_source_current(db: Session, record: MemoryRecord) -> None:
    """Fail closed when a graph proposal or its Worker source snapshot has changed."""
    structured_data = record.structured_data_json or {}
    proposal = _memory_graph_proposal_for_record(record)
    if proposal is None:
        raise HTTPException(status_code=409, detail="Graph proposal is invalid; regenerate it before approval")
    try:
        proposal.validate_evidence_sources(
            {(link.source_type, link.source_id) for link in record.evidence_links}
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail="Graph proposal evidence is no longer valid; regenerate it",
        ) from exc

    source_memory_record_id = structured_data.get("source_memory_record_id")
    if not isinstance(source_memory_record_id, str) or not source_memory_record_id:
        # Manually proposed graph notes have no Worker source snapshot, but the
        # proposal's own canonical evidence links were revalidated above.
        return
    if structured_data.get("graph_policy_version") != _MEMORY_GRAPH_PROPOSER_POLICY_VERSION:
        raise HTTPException(status_code=409, detail="Graph proposal policy is no longer supported; regenerate it")
    source_record = db.scalar(
        select(MemoryRecord).where(MemoryRecord.id == source_memory_record_id).with_for_update()
    )
    if (
        source_record is None
        or source_record.org_id != record.org_id
        or source_record.project_id != record.project_id
        or source_record.scope != MemoryScope.PROJECT_SHARED.value
        or source_record.status != MemoryStatus.ACTIVE.value
        or source_record.deleted_at is not None
        or (source_record.expires_at is not None and source_record.expires_at <= _utc_naive_now())
    ):
        raise HTTPException(status_code=409, detail="Graph proposal source is no longer active; regenerate it")
    source_links = list(
        db.scalars(
            select(MemoryEvidenceLink)
            .where(MemoryEvidenceLink.memory_record_id == source_record.id)
            .order_by(MemoryEvidenceLink.id.asc())
            .with_for_update()
        ).all()
    )
    if not source_links or record.content_fingerprint != _memory_graph_snapshot_fingerprint(source_record, source_links):
        raise HTTPException(status_code=409, detail="Graph proposal source changed; regenerate it before approval")
    try:
        proposal.validate_evidence_sources(
            {(link.source_type, link.source_id) for link in source_links}
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail="Graph proposal source evidence changed; regenerate it before approval",
        ) from exc


def _require_create_scope_access(db: Session, current_user: CurrentUser, payload: MemoryCreate) -> None:
    if payload.scope is MemoryScope.USER_PRIVATE:
        if payload.project_id:
            require_project_capability(
                db,
                current_user=current_user,
                project_id=payload.project_id,
                capability="memory.read",
            )
        return
    if payload.scope is MemoryScope.ORG_SHARED:
        raise HTTPException(status_code=403, detail="Organization-shared memory is not enabled for direct writes")
    if not payload.project_id:
        raise HTTPException(status_code=422, detail="project_id is required for project-shared memory")
    require_project_capability(
        db,
        current_user=current_user,
        project_id=payload.project_id,
        capability="memory.propose",
    )
    if payload.kind in {MemoryKind.FACT, MemoryKind.PROCEDURE, MemoryKind.RISK} and not payload.citations:
        raise HTTPException(status_code=422, detail="Evidence is required for shared factual memory")


def _canonicalize_client_citations(
    db: Session,
    *,
    current_user: CurrentUser,
    project_id: str | None,
    citations: tuple[MemoryCitation, ...],
) -> tuple[MemoryCitation, ...]:
    """Accept only real, caller-authorized sources and never trust client labels.

    A citation ID is an authorization boundary, not presentation metadata. This
    keeps a contributor from turning an arbitrary UUID (or another project's
    evidence) into a seemingly grounded shared-memory fact. Manual memory has
    an explicit human-decision provenance instead of a fabricated document link.
    """
    if not citations:
        return (
            MemoryCitation(
                source_type=MemoryCitationSource.HUMAN_DECISION,
                source_id=current_user.id,
                label="用户明确写入",
            ),
        )
    return tuple(
        _canonicalize_client_citation(
            db,
            current_user=current_user,
            project_id=project_id,
            citation=citation,
        )
        for citation in citations
    )


def _validate_memory_graph_proposal(payload: MemoryCreate, citations: tuple[MemoryCitation, ...]) -> None:
    """Validate a future graph proposal before it can enter the review queue.

    Entity/relation rows are not materialized in this phase. This check only
    guarantees that a structured proposal cannot name sources outside the
    server-canonicalized evidence attached to the MemoryRecord.
    """
    structured_data = payload.structured_data_json
    if not isinstance(structured_data, dict):
        return
    graph_payload = structured_data.get("memory_graph_proposal")
    if graph_payload is None:
        return
    if payload.scope is not MemoryScope.PROJECT_SHARED or payload.kind is not MemoryKind.ENTITY_NOTE:
        raise HTTPException(
            status_code=422,
            detail="Memory graph proposals require project-shared entity-note memory",
        )
    if not payload.citations:
        raise HTTPException(status_code=422, detail="Memory graph proposals require explicit project evidence")
    if not isinstance(graph_payload, dict):
        raise HTTPException(status_code=422, detail="Memory graph proposal has an invalid structure")
    try:
        proposal = MemoryGraphProposal.model_validate(graph_payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Memory graph proposal has an invalid structure") from exc
    try:
        proposal.validate_evidence_sources({(citation.source_type.value, citation.source_id) for citation in citations})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Memory graph proposal references unavailable evidence") from exc


def _canonicalize_client_citation(
    db: Session,
    *,
    current_user: CurrentUser,
    project_id: str | None,
    citation: MemoryCitation,
) -> MemoryCitation:
    if citation.source_type is MemoryCitationSource.HUMAN_DECISION:
        # The server creates this provenance for manual writes; clients cannot
        # manufacture a different person's approval record.
        raise _invalid_memory_citation()

    if citation.source_type is MemoryCitationSource.KNOWLEDGE_CHUNK:
        row = db.execute(
            select(KnowledgeChunk, SourceDocument, Bundle)
            .join(SourceDocument, SourceDocument.id == KnowledgeChunk.source_document_id)
            .join(Bundle, Bundle.id == SourceDocument.bundle_id)
            .where(KnowledgeChunk.id == citation.source_id)
        ).one_or_none()
        if row is None:
            raise _invalid_memory_citation()
        chunk, source, bundle = row
        if chunk.project_id != project_id or bundle.project_id != project_id:
            raise _invalid_memory_citation()
        metadata = chunk.metadata_json if isinstance(chunk.metadata_json, dict) else {}
        locator: dict[str, object] = {
            "source_document_id": source.id,
            "chunk_index": chunk.chunk_index,
        }
        for key in ("page", "heading_path", "table_headers"):
            if key in metadata:
                locator[key] = metadata[key]
        return MemoryCitation(
            source_type=citation.source_type,
            source_id=chunk.id,
            label=f"{source.original_filename} · 片段 {chunk.chunk_index + 1}",
            locator_json=locator,
        )

    if citation.source_type is MemoryCitationSource.REQUIREMENT_ITEM:
        requirement = db.get(RequirementItem, citation.source_id)
        if requirement is None or requirement.project_id != project_id:
            raise _invalid_memory_citation()
        return MemoryCitation(
            source_type=citation.source_type,
            source_id=requirement.id,
            label=f"要求项 {requirement.section_key}",
            locator_json=requirement.source_locator_json,
        )

    if citation.source_type is MemoryCitationSource.EVIDENCE_ITEM:
        evidence = db.get(Evidence, citation.source_id)
        if evidence is None or evidence.project_id != project_id:
            raise _invalid_memory_citation()
        return MemoryCitation(
            source_type=citation.source_type,
            source_id=evidence.id,
            label=f"证据记录 {evidence.id[:8]}",
            locator_json=evidence.locator_json,
        )

    if citation.source_type is MemoryCitationSource.CHAT_MESSAGE:
        conversation = db.scalar(
            select(ChatConversation)
            .join(ChatMessage, ChatMessage.conversation_id == ChatConversation.id)
            .where(
                ChatMessage.id == citation.source_id,
                ChatConversation.user_id == current_user.id,
            )
        )
        if conversation is None or conversation.project_id != project_id:
            raise _invalid_memory_citation()
        return MemoryCitation(
            source_type=citation.source_type,
            source_id=citation.source_id,
            label="当前会话消息",
        )

    if citation.source_type is MemoryCitationSource.AUDIT_EVENT:
        event = db.get(AuditEvent, citation.source_id)
        if event is None or event.project_id != project_id:
            raise _invalid_memory_citation()
        return MemoryCitation(
            source_type=citation.source_type,
            source_id=event.id,
            label=f"项目操作记录：{event.event_type}",
            locator_json={"occurred_at": event.created_at.isoformat()} if event.created_at else None,
        )

    raise _invalid_memory_citation()


def _invalid_memory_citation() -> HTTPException:
    return HTTPException(status_code=422, detail="Memory citation is not valid for this project")


def _require_record_for_project_action(
    db: Session,
    memory_id: str,
    current_user: CurrentUser,
    *,
    capability: str,
) -> MemoryRecord:
    # Serialize approval and per-item decisions for one proposal. This closes
    # the race where a reviewer reads `proposed` just before another reviewer
    # activates the record, then commits a late decision after activation.
    record = db.scalar(select(MemoryRecord).where(MemoryRecord.id == memory_id).with_for_update())
    if record is None or record.org_id != _org_id(current_user):
        raise HTTPException(status_code=404, detail="Memory record not found")
    if record.scope == MemoryScope.USER_PRIVATE.value or not record.project_id:
        raise HTTPException(status_code=403, detail="This memory record is not a project approval item")
    require_project_capability(
        db,
        current_user=current_user,
        project_id=record.project_id,
        capability=capability,
    )
    return record


def _citation_link(memory_record_id: str, citation: MemoryCitation) -> MemoryEvidenceLink:
    return MemoryEvidenceLink(
        memory_record_id=memory_record_id,
        source_type=citation.source_type.value,
        source_id=citation.source_id,
        label=citation.label,
        locator_json=citation.locator_json,
    )


def _record_event(
    db: Session,
    record: MemoryRecord,
    current_user: CurrentUser,
    event_type: str,
    payload: dict | None,
) -> None:
    db.add(
        MemoryEvent(
            memory_record_id=record.id,
            org_id=record.org_id,
            project_id=record.project_id,
            actor_type="user",
            actor_id=current_user.id,
            event_type=event_type,
            payload_json=payload,
        )
    )


def _request_memory_embedding_index(
    db: Session,
    record: MemoryRecord,
    current_user: CurrentUser,
) -> None:
    """Queue semantic indexing after durable activation without blocking the write.

    Memory remains available through the lexical retrieval path whenever the
    platform embedding provider or the caller's official indexing allowance is
    unavailable. A failed queue dispatch also removes the provisional usage
    charge, so user-visible activation never becomes an untraceable billable
    event.
    """
    from app.retrieval.embedding import get_embedding_profile

    profile = get_embedding_profile()
    if profile is None:
        _record_event(
            db,
            record,
            current_user,
            "memory.embedding_deferred",
            {"reason": "embedding_not_configured"},
        )
        db.commit()
        return
    if record.embedding_status == "success" and record.embedding_profile == profile.identifier:
        return

    try:
        check_indexing_quota(db, current_user.id, _org_id(current_user), ProviderSource.OFFICIAL)
    except UsageLimitExceeded:
        _record_event(
            db,
            record,
            current_user,
            "memory.embedding_deferred",
            {"reason": "official_indexing_quota_exhausted"},
        )
        db.commit()
        return

    usage_event = record_usage_event(
        db,
        user_id=current_user.id,
        org_id=_org_id(current_user),
        project_id=record.project_id,
        event_type=EMBEDDING_INDEX_STARTED,
        provider_source=ProviderSource.OFFICIAL,
        metadata_json={"memory_record_id": record.id, "action": "index_memory"},
    )
    _record_event(
        db,
        record,
        current_user,
        "memory.embedding_index_requested",
        {"profile_id": profile.identifier},
    )
    try:
        celery.send_task("worker.index_memory_records", args=[[record.id]])
    except Exception:
        # The task never entered the broker, so do not retain a charge for it.
        db.delete(usage_event)
        _record_event(
            db,
            record,
            current_user,
            "memory.embedding_dispatch_failed",
            {"reason": "task_dispatch_failed"},
        )
        logger.warning("Could not queue memory indexing for record %s", record.id)
    db.commit()


def _to_read(record: MemoryRecord) -> MemoryRead:
    return MemoryRead(
        id=record.id,
        org_id=record.org_id,
        project_id=record.project_id,
        owner_user_id=record.owner_user_id,
        scope=MemoryScope(record.scope),
        kind=MemoryKind(record.kind),
        status=MemoryStatus(record.status),
        title=record.title,
        body_markdown=record.body_markdown,
        citations=[
            MemoryCitation(
                source_type=link.source_type,
                source_id=link.source_id,
                label=link.label,
                locator_json=link.locator_json,
            )
            for link in record.evidence_links
        ],
        graph_proposal=_graph_proposal_for_read(record),
        expires_at=record.expires_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _graph_proposal_for_read(record: MemoryRecord) -> MemoryGraphProposalRead | None:
    proposal = _memory_graph_proposal_for_record(record)
    if proposal is None:
        return None
    proposal_fingerprint = _graph_proposal_fingerprint(proposal)
    decisions = {
        decision.item_id: decision
        for decision in record.graph_review_decisions
        if decision.proposal_fingerprint == proposal_fingerprint
    }
    evidence_labels = {
        (link.source_type, link.source_id): link.label
        for link in record.evidence_links
    }
    entities_by_local_id = {entity.local_id: entity.canonical_name for entity in proposal.entities}
    return MemoryGraphProposalRead(
        schema_version=proposal.schema_version,
        entities=tuple(
            MemoryGraphEntityRead(
                item_id=_graph_item_id(proposal_fingerprint, "entity", entity.semantic_key),
                canonical_name=entity.canonical_name,
                entity_type=entity.entity_type,
                evidence_labels=tuple(
                    evidence_labels.get(evidence_ref.key, "已验证来源")
                    for evidence_ref in entity.evidence_refs
                ),
                review_status=decisions.get(
                    _graph_item_id(proposal_fingerprint, "entity", entity.semantic_key)
                ).decision
                if decisions.get(_graph_item_id(proposal_fingerprint, "entity", entity.semantic_key))
                else "pending",
                review_note=decisions.get(
                    _graph_item_id(proposal_fingerprint, "entity", entity.semantic_key)
                ).decision_note
                if decisions.get(_graph_item_id(proposal_fingerprint, "entity", entity.semantic_key))
                else None,
            )
            for entity in proposal.entities
        ),
        relations=tuple(
            MemoryGraphRelationRead(
                item_id=_graph_item_id(
                    proposal_fingerprint,
                    "relation",
                    (
                        entities_by_local_id[relation.subject_local_id],
                        relation.predicate.value,
                        entities_by_local_id[relation.object_local_id],
                    ),
                ),
                subject=entities_by_local_id[relation.subject_local_id],
                predicate=relation.predicate,
                object=entities_by_local_id[relation.object_local_id],
                evidence_labels=tuple(
                    evidence_labels.get(evidence_ref.key, "已验证来源")
                    for evidence_ref in relation.evidence_refs
                ),
                review_status=(
                    decisions.get(
                        _graph_item_id(
                            proposal_fingerprint,
                            "relation",
                            (
                                entities_by_local_id[relation.subject_local_id],
                                relation.predicate.value,
                                entities_by_local_id[relation.object_local_id],
                            ),
                        )
                    ).decision
                    if decisions.get(
                        _graph_item_id(
                            proposal_fingerprint,
                            "relation",
                            (
                                entities_by_local_id[relation.subject_local_id],
                                relation.predicate.value,
                                entities_by_local_id[relation.object_local_id],
                            ),
                        )
                    )
                    else "pending"
                ),
                review_note=(
                    decisions.get(
                        _graph_item_id(
                            proposal_fingerprint,
                            "relation",
                            (
                                entities_by_local_id[relation.subject_local_id],
                                relation.predicate.value,
                                entities_by_local_id[relation.object_local_id],
                            ),
                        )
                    ).decision_note
                    if decisions.get(
                        _graph_item_id(
                            proposal_fingerprint,
                            "relation",
                            (
                                entities_by_local_id[relation.subject_local_id],
                                relation.predicate.value,
                                entities_by_local_id[relation.object_local_id],
                            ),
                        )
                    )
                    else None
                ),
            )
            for relation in proposal.relations
        ),
    )


def _memory_graph_proposal_for_record(record: MemoryRecord) -> MemoryGraphProposal | None:
    structured_data = record.structured_data_json or {}
    candidate = structured_data.get("memory_graph_proposal")
    if not isinstance(candidate, dict):
        return None
    try:
        return MemoryGraphProposal.model_validate(candidate)
    except ValueError:
        logger.warning("Ignoring invalid stored memory graph proposal: record=%s", record.id)
        return None


def _graph_proposal_fingerprint(proposal: MemoryGraphProposal) -> str:
    return memory_graph_proposal_fingerprint(proposal)


def _graph_item_id(proposal_fingerprint: str, item_type: str, item_key: object) -> str:
    if item_type not in {"entity", "relation"}:
        raise ValueError("unsupported memory graph item type")
    return memory_graph_item_id(proposal_fingerprint, item_type, item_key)


def _graph_item_type_for_id(proposal: MemoryGraphProposal, proposal_fingerprint: str, item_id: str) -> str | None:
    entity_ids = {_graph_item_id(proposal_fingerprint, "entity", entity.semantic_key) for entity in proposal.entities}
    if item_id in entity_ids:
        return "entity"
    entities_by_local_id = {entity.local_id: entity for entity in proposal.entities}
    relation_ids = {
        _graph_item_id(
            proposal_fingerprint,
            "relation",
            (
                entities_by_local_id[relation.subject_local_id].canonical_name,
                relation.predicate.value,
                entities_by_local_id[relation.object_local_id].canonical_name,
            ),
        )
        for relation in proposal.relations
    }
    return "relation" if item_id in relation_ids else None


def _graph_proposal_pending_item_count(record: MemoryRecord, proposal: MemoryGraphProposal) -> int:
    fingerprint = _graph_proposal_fingerprint(proposal)
    decisions = {
        decision.item_id: decision
        for decision in record.graph_review_decisions
        if decision.proposal_fingerprint == fingerprint
    }
    item_ids = {
        _graph_item_id(fingerprint, "entity", entity.semantic_key)
        for entity in proposal.entities
    }
    entities_by_local_id = {entity.local_id: entity for entity in proposal.entities}
    item_ids.update(
        _graph_item_id(
            fingerprint,
            "relation",
            (
                entities_by_local_id[relation.subject_local_id].canonical_name,
                relation.predicate.value,
                entities_by_local_id[relation.object_local_id].canonical_name,
            ),
        )
        for relation in proposal.relations
    )
    return sum(item_id not in decisions for item_id in item_ids)


def _to_compilation_read(run: MemoryCompilationRun) -> MemoryCompilationRead:
    return MemoryCompilationRead(
        id=run.id,
        project_id=run.project_id,
        bundle_id=run.bundle_id,
        status=run.status,
        input_source_count=len(run.input_source_ids_json),
        result_json=run.result_json,
        error_code=run.error_code,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def _org_id(current_user: CurrentUser) -> str:
    return current_user.org_id or "default"


def _utc_naive_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
