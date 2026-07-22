"""Build one reviewable entity/relation proposal from approved project memory."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.adapters.memory_graph import extract_memory_graph
from app.adapters.provider_errors import ProviderInvocationError
from app.db import SessionLocal
from app.execution.model_usage import (
    begin_workflow_model_call,
    finalize_workflow_model_reservation_failure,
    record_workflow_model_usage,
)
from app.models import ExecutionRun, MemoryEvent, MemoryEvidenceLink, MemoryRecord
from app.provider_registry import get_provider_by_id
from contracts import (
    MemoryCitation,
    MemoryGraphProposal,
    MemoryScope,
    MemoryStatus,
    memory_graph_source_snapshot_fingerprint,
    normalize_retrieval_text,
)


_POLICY_VERSION = "memory-graph-proposer-v1"


def run_extract_memory_graph(
    run_id: str,
    project_id: str,
    memory_record_id: str,
    *,
    provider_config_id: str | None = None,
    reasoning_effort: str | None = None,
) -> dict[str, str]:
    """Call a provider once and persist only a reviewable graph proposal.

    The source memory is read before and after provider dispatch. If its source
    snapshot changed while the model was running, the paid result is discarded
    instead of being attached to stale evidence.
    """
    source = _load_source_snapshot(run_id, project_id, memory_record_id)
    existing = _find_existing_graph_proposal(project_id, source.snapshot_fingerprint)
    if existing is not None:
        finalize_workflow_model_reservation_failure(run_id=run_id, error_code="memory_graph_reused")
        return _finish_reused_run(run_id, existing.id)

    provider_config = _provider_config(provider_config_id)
    model_call = begin_workflow_model_call(
        run_id=run_id,
        workload="memory_graph_extraction",
        operation_key="memory-graph-extraction",
    )
    try:
        result = extract_memory_graph(
            title=source.title,
            body_markdown=source.body_markdown,
            citations=source.citations,
            provider_config=provider_config,
            reasoning_effort=reasoning_effort,
        )
    except ProviderInvocationError:
        raise

    record_workflow_model_usage(
        run_id=run_id,
        provider_type=provider_config["provider_type"] if provider_config is not None else "openai",
        model_name=result.model_used,
        measurement=result.usage,
        workload="memory_graph_extraction",
        reservation_key=model_call.reservation_key,
    )
    return _persist_graph_proposal(run_id, source, result.proposal)


class _SourceSnapshot:
    def __init__(
        self,
        *,
        org_id: str,
        project_id: str,
        source_memory_id: str,
        title: str,
        body_markdown: str,
        citations: tuple[MemoryCitation, ...],
        snapshot_fingerprint: str,
    ) -> None:
        self.org_id = org_id
        self.project_id = project_id
        self.source_memory_id = source_memory_id
        self.title = title
        self.body_markdown = body_markdown
        self.citations = citations
        self.snapshot_fingerprint = snapshot_fingerprint


def _load_source_snapshot(run_id: str, project_id: str, memory_record_id: str) -> _SourceSnapshot:
    db = SessionLocal()
    try:
        run = db.get(ExecutionRun, run_id)
        if run is None or run.project_id != project_id:
            raise _input_error("memory_graph_run_not_found")
        input_json = run.input_json or {}
        if input_json.get("memory_record_id") != memory_record_id:
            raise _input_error("memory_graph_input_invalid")
        if input_json.get("graph_policy_version") != _POLICY_VERSION:
            raise _input_error("memory_graph_policy_unsupported")
        source = db.get(MemoryRecord, memory_record_id)
        if not _is_eligible_source(source, project_id):
            raise _input_error("memory_graph_source_not_eligible")
        citations = _load_citations(db, source.id)
        if not citations:
            raise _input_error("memory_graph_source_not_eligible")
        fingerprint = _snapshot_fingerprint(source, citations)
        if input_json.get("source_snapshot_fingerprint") != fingerprint:
            raise _input_error("memory_graph_source_changed_before_dispatch")
        run.status = "running"
        run.started_at = _utc_naive_now()
        db.commit()
        return _SourceSnapshot(
            org_id=source.org_id,
            project_id=source.project_id or project_id,
            source_memory_id=source.id,
            title=source.title,
            body_markdown=source.body_markdown,
            citations=citations,
            snapshot_fingerprint=fingerprint,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _persist_graph_proposal(
    run_id: str,
    source: _SourceSnapshot,
    proposal: MemoryGraphProposal,
) -> dict[str, str]:
    db = SessionLocal()
    try:
        run = db.get(ExecutionRun, run_id)
        if run is None:
            raise _input_error("memory_graph_run_not_found")
        current_source = db.get(MemoryRecord, source.source_memory_id)
        if not _is_eligible_source(current_source, source.project_id):
            raise _input_error("memory_graph_source_not_eligible")
        current_citations = _load_citations(db, current_source.id)
        if _snapshot_fingerprint(current_source, current_citations) != source.snapshot_fingerprint:
            raise _input_error("memory_graph_source_changed_after_dispatch")
        proposal.validate_evidence_sources(
            {(citation.source_type.value, citation.source_id) for citation in current_citations}
        )

        existing = _find_existing_graph_proposal_in_session(db, source.project_id, source.snapshot_fingerprint)
        if existing is not None:
            return _finish_reused_run_in_session(db, run, existing.id)

        proposal_record = MemoryRecord(
            org_id=source.org_id,
            project_id=source.project_id,
            owner_user_id=None,
            scope=MemoryScope.PROJECT_SHARED.value,
            kind="entity_note",
            status=MemoryStatus.PROPOSED.value,
            title=f"{source.title[:180]} · 实体关系提案",
            body_markdown=(
                f"基于已批准知识「{source.title[:180]}」生成了待审核的实体关系提案。\n\n"
                f"- 实体：{len(proposal.entities)}\n"
                f"- 关系：{len(proposal.relations)}\n\n"
                "请核对每条关系及其来源后再批准。"
            ),
            structured_data_json={
                "memory_graph_proposal": proposal.model_dump(mode="json"),
                "source_memory_record_id": source.source_memory_id,
                "graph_policy_version": _POLICY_VERSION,
            },
            content_fingerprint=source.snapshot_fingerprint,
            retrieval_text=normalize_retrieval_text(f"{source.title} 实体关系提案"),
            embedding_status="pending",
            origin="system",
            created_by_actor_type="system",
            created_by_actor_id="memory-graph-proposer",
        )
        db.add(proposal_record)
        db.flush()
        for citation in current_citations:
            db.add(
                MemoryEvidenceLink(
                    memory_record_id=proposal_record.id,
                    source_type=citation.source_type.value,
                    source_id=citation.source_id,
                    evidence_role="derived_from",
                    label=citation.label,
                    locator_json=citation.locator_json,
                )
            )
        db.add(
            MemoryEvent(
                memory_record_id=proposal_record.id,
                org_id=source.org_id,
                project_id=source.project_id,
                actor_type="system",
                actor_id="memory-graph-proposer",
                event_type="memory.graph_proposed",
                payload_json={
                    "execution_run_id": run.id,
                    "source_memory_record_id": source.source_memory_id,
                    "entity_count": len(proposal.entities),
                    "relation_count": len(proposal.relations),
                    "policy_version": _POLICY_VERSION,
                },
            )
        )
        run.status = "succeeded"
        run.finished_at = _utc_naive_now()
        run.output_json = {
            "proposal_memory_id": proposal_record.id,
            "entity_count": len(proposal.entities),
            "relation_count": len(proposal.relations),
            "reused": False,
        }
        db.commit()
        return {
            "run_id": run.id,
            "status": "succeeded",
            "proposal_memory_id": proposal_record.id,
            "entity_count": str(len(proposal.entities)),
            "relation_count": str(len(proposal.relations)),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _provider_config(provider_config_id: str | None) -> dict[str, object] | None:
    if provider_config_id is None:
        return None
    config = get_provider_by_id(provider_config_id)
    if config is None:
        raise ProviderInvocationError(
            "provider_config_missing",
            "所选模型提供商配置已不可用，请重新选择后再试。",
            retryable=False,
        )
    return {
        "provider_type": config.provider_type,
        "provider_id": config.provider_id,
        "api_key": config.api_key,
        "api_url": config.api_url,
        "model": config.model,
    }


def _find_existing_graph_proposal(project_id: str, fingerprint: str) -> MemoryRecord | None:
    db = SessionLocal()
    try:
        return _find_existing_graph_proposal_in_session(db, project_id, fingerprint)
    finally:
        db.close()


def _find_existing_graph_proposal_in_session(db, project_id: str, fingerprint: str) -> MemoryRecord | None:
    return db.scalar(
        select(MemoryRecord)
        .where(
            MemoryRecord.project_id == project_id,
            MemoryRecord.content_fingerprint == fingerprint,
            MemoryRecord.kind == "entity_note",
            MemoryRecord.status.in_((MemoryStatus.PROPOSED.value, MemoryStatus.ACTIVE.value)),
            MemoryRecord.deleted_at.is_(None),
        )
        .limit(1)
    )


def _finish_reused_run(run_id: str, proposal_memory_id: str) -> dict[str, str]:
    db = SessionLocal()
    try:
        run = db.get(ExecutionRun, run_id)
        if run is None:
            raise _input_error("memory_graph_run_not_found")
        return _finish_reused_run_in_session(db, run, proposal_memory_id)
    finally:
        db.close()


def _finish_reused_run_in_session(db, run: ExecutionRun, proposal_memory_id: str) -> dict[str, str]:
    run.status = "succeeded"
    run.finished_at = _utc_naive_now()
    run.output_json = {"proposal_memory_id": proposal_memory_id, "reused": True}
    db.commit()
    return {"run_id": run.id, "status": "succeeded", "proposal_memory_id": proposal_memory_id, "reused": "true"}


def _load_citations(db, memory_record_id: str) -> tuple[MemoryCitation, ...]:
    links = list(
        db.scalars(
            select(MemoryEvidenceLink)
            .where(MemoryEvidenceLink.memory_record_id == memory_record_id)
            .order_by(MemoryEvidenceLink.id.asc())
        ).all()
    )
    return tuple(
        MemoryCitation(
            source_type=link.source_type,
            source_id=link.source_id,
            label=link.label,
            locator_json=link.locator_json,
        )
        for link in links
    )


def _is_eligible_source(record: MemoryRecord | None, project_id: str) -> bool:
    return bool(
        record
        and record.project_id == project_id
        and record.scope == MemoryScope.PROJECT_SHARED.value
        and record.status == MemoryStatus.ACTIVE.value
        and record.deleted_at is None
        and (record.expires_at is None or record.expires_at > _utc_naive_now())
    )


def _snapshot_fingerprint(record: MemoryRecord, citations: tuple[MemoryCitation, ...]) -> str:
    return memory_graph_source_snapshot_fingerprint(
        policy_version=_POLICY_VERSION,
        memory_record_id=record.id,
        title=record.title,
        body_markdown=record.body_markdown,
        citations=citations,
    )


def _input_error(error_code: str) -> ProviderInvocationError:
    return ProviderInvocationError(
        error_code,
        "用于生成实体关系提案的知识已变化或不可用，请刷新后重试。",
        retryable=False,
    )


def _utc_naive_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
