from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters.memory_graph import MemoryGraphExtractionResult
from app.adapters.provider_errors import ProviderInvocationError
from app.execution.memory_graph import _snapshot_fingerprint, run_extract_memory_graph
from app.models import ExecutionRun, MemoryEntity, MemoryEvidenceLink, MemoryRecord, MemoryRelation, Organization, Project
from contracts import (
    MemoryCitation,
    MemoryGraphEvidenceRef,
    MemoryGraphEntityProposal,
    MemoryGraphEntityType,
    MemoryGraphProposal,
    MemoryGraphRelationPredicate,
    MemoryGraphRelationProposal,
    normalize_retrieval_text,
)
from contracts.models import Base


def _suffix() -> str:
    return uuid4().hex[:10]


@pytest.fixture()
def graph_session(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr("app.execution.memory_graph.SessionLocal", SessionLocal)
    monkeypatch.setattr("app.execution.model_usage.SessionLocal", SessionLocal)
    return SessionLocal


def _seed_graph_extraction(SessionLocal) -> tuple[str, str, str]:
    suffix = _suffix()
    db = SessionLocal()
    try:
        org = Organization(id=f"org-graph-{suffix}", slug=f"graph-{suffix}", name="Graph Test")
        project = Project(
            id=f"project-graph-{suffix}",
            org_id=org.id,
            slug=f"graph-{suffix}",
            name="Graph Test",
            scenario_package="bidpilot",
        )
        source = MemoryRecord(
            org_id=org.id,
            project_id=project.id,
            scope="project_shared",
            kind="fact",
            status="active",
            title="私有化部署要求",
            body_markdown="投标方案必须说明私有化部署方案。",
            retrieval_text=normalize_retrieval_text("投标方案必须说明私有化部署方案。"),
            embedding_status="pending",
            origin="system",
            created_by_actor_type="system",
            created_by_actor_id="memory-test",
        )
        db.add_all([org, project, source])
        db.flush()
        evidence = MemoryEvidenceLink(
            memory_record_id=source.id,
            source_type="knowledge_chunk",
            source_id=f"chunk-{suffix}",
            evidence_role="supports",
            label="技术规范 · 片段 1",
            locator_json={"chunk_index": 0},
        )
        db.add(evidence)
        db.flush()
        db.refresh(source)
        fingerprint = _snapshot_fingerprint(
            source,
            (
                MemoryCitation(
                    source_type=evidence.source_type,
                    source_id=evidence.source_id,
                    label=evidence.label,
                    locator_json=evidence.locator_json,
                ),
            ),
        )
        run = ExecutionRun(
            project_id=project.id,
            run_type="memory_graph_extraction",
            input_json={
                "memory_record_id": source.id,
                "source_snapshot_fingerprint": fingerprint,
                "graph_policy_version": "memory-graph-proposer-v1",
            },
        )
        db.add(run)
        db.commit()
        return run.id, project.id, source.id
    finally:
        db.close()


def _proposal(source_id: str) -> MemoryGraphProposal:
    evidence = MemoryGraphEvidenceRef(source_type="knowledge_chunk", source_id=source_id)
    return MemoryGraphProposal(
        entities=(
            MemoryGraphEntityProposal(
                local_id="deployment",
                canonical_name="私有化部署",
                entity_type=MemoryGraphEntityType.REQUIREMENT,
                evidence_refs=(evidence,),
            ),
            MemoryGraphEntityProposal(
                local_id="proposal",
                canonical_name="投标方案",
                entity_type=MemoryGraphEntityType.DELIVERABLE,
                evidence_refs=(evidence,),
            ),
        ),
        relations=(
            MemoryGraphRelationProposal(
                subject_local_id="deployment",
                predicate=MemoryGraphRelationPredicate.REQUIRES,
                object_local_id="proposal",
                evidence_refs=(evidence,),
            ),
        ),
    )


def test_graph_extraction_creates_only_a_reviewable_memory_proposal(
    graph_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id, project_id, source_memory_id = _seed_graph_extraction(graph_session)
    db = graph_session()
    try:
        source_link = db.query(MemoryEvidenceLink).filter_by(memory_record_id=source_memory_id).one()
        source_id = source_link.source_id
    finally:
        db.close()

    monkeypatch.setattr(
        "app.execution.memory_graph.extract_memory_graph",
        lambda **_kwargs: MemoryGraphExtractionResult(
            proposal=_proposal(source_id),
            model_used="test-model",
            usage=None,
        ),
    )

    result = run_extract_memory_graph(run_id, project_id, source_memory_id)

    assert result["status"] == "succeeded"
    assert result["entity_count"] == "2"
    assert result["relation_count"] == "1"
    db = graph_session()
    try:
        run = db.get(ExecutionRun, run_id)
        assert run is not None
        assert run.status == "succeeded"
        proposal = db.get(MemoryRecord, result["proposal_memory_id"])
        assert proposal is not None
        assert proposal.status == "proposed"
        assert proposal.kind == "entity_note"
        assert proposal.origin == "system"
        assert proposal.structured_data_json["source_memory_record_id"] == source_memory_id
        assert proposal.structured_data_json["memory_graph_proposal"]["relations"][0]["predicate"] == "requires"
        proposal_links = db.query(MemoryEvidenceLink).filter_by(memory_record_id=proposal.id).all()
        assert [(link.source_type, link.source_id, link.evidence_role) for link in proposal_links] == [
            ("knowledge_chunk", source_id, "derived_from")
        ]
        assert db.query(MemoryEntity).filter_by(project_id=project_id).count() == 0
        assert db.query(MemoryRelation).filter_by(project_id=project_id).count() == 0
    finally:
        db.close()


def test_graph_extraction_rejects_changed_source_before_provider_call(
    graph_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id, project_id, source_memory_id = _seed_graph_extraction(graph_session)
    db = graph_session()
    try:
        source = db.get(MemoryRecord, source_memory_id)
        assert source is not None
        source.body_markdown = "已修改的知识内容。"
        db.commit()
    finally:
        db.close()

    called = False

    def should_not_call(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("provider must not run for stale source memory")

    monkeypatch.setattr("app.execution.memory_graph.extract_memory_graph", should_not_call)

    with pytest.raises(ProviderInvocationError) as error:
        run_extract_memory_graph(run_id, project_id, source_memory_id)

    assert error.value.error_code == "memory_graph_source_changed_before_dispatch"
    assert called is False
