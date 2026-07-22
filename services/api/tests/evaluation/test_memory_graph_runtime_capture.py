from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.evaluation.memory_graph_metrics import (
    MemoryGraphBenchmarkCase,
    MemoryGraphBenchmarkDataset,
    MemoryGraphBenchmarkEntity,
    MemoryGraphBenchmarkRelation,
    fixture_fingerprint,
    score_memory_graph_run,
)
from app.evaluation.memory_graph_runtime_capture import (
    MemoryGraphRuntimeCaptureItem,
    MemoryGraphRuntimeCaptureManifest,
    MemoryGraphRuntimeEvidenceMap,
    capture_memory_graph_runtime_run,
)
from app.models import (
    ExecutionRun,
    MemoryEvidenceLink,
    MemoryGraphReviewDecision,
    MemoryRecord,
    Project,
    RuntimeRun,
)
from contracts import (
    EvaluationCaptureKind,
    EvaluationEvidenceProvenance,
    EvaluationReviewLevel,
    MemoryCitation,
    MemoryGraphEvidenceRef,
    MemoryGraphEntityProposal,
    MemoryGraphEntityType,
    MemoryGraphProposal,
    MemoryGraphRelationPredicate,
    MemoryGraphRelationProposal,
    RuntimeRunStatus,
    memory_graph_item_id,
    memory_graph_proposal_fingerprint,
    memory_graph_source_snapshot_fingerprint,
    normalize_retrieval_text,
)


_POLICY_VERSION = "memory-graph-proposer-v1"
_MODEL = "controlled-graph-model"


def _proposal(actual_source_id: str) -> MemoryGraphProposal:
    evidence = MemoryGraphEvidenceRef(source_type="knowledge_chunk", source_id=actual_source_id)
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


def _dataset() -> MemoryGraphBenchmarkDataset:
    deployment = MemoryGraphBenchmarkEntity(
        canonical_name="私有化部署",
        entity_type=MemoryGraphEntityType.REQUIREMENT,
    )
    proposal = MemoryGraphBenchmarkEntity(
        canonical_name="投标方案",
        entity_type=MemoryGraphEntityType.DELIVERABLE,
    )
    evidence = MemoryGraphEvidenceRef(source_type="knowledge_chunk", source_id="benchmark-chunk")
    return MemoryGraphBenchmarkDataset(
        dataset_id="memory-graph-runtime-capture-v1",
        title="Runtime graph capture",
        dataset_role="controlled",
        cases=(
            MemoryGraphBenchmarkCase(
                id="private-deployment",
                org_id="benchmark-org",
                project_id="benchmark-project",
                memory_record_id="benchmark-memory",
                available_evidence_refs=(evidence,),
                expected_entities=(deployment, proposal),
                expected_relations=(
                    MemoryGraphBenchmarkRelation(
                        subject=deployment,
                        predicate=MemoryGraphRelationPredicate.REQUIRES,
                        object=proposal,
                        expected_evidence_refs=(evidence,),
                    ),
                ),
            ),
        ),
    )


def _seed_capture_records(test_db, default_org_id: str, default_user_id: str) -> dict[str, str]:
    suffix = uuid4().hex[:10]
    project = Project(
        id=str(uuid4()),
        org_id=default_org_id,
        slug=f"graph-capture-{suffix}",
        name="Graph Capture",
        scenario_package="bidpilot",
    )
    test_db.add(project)
    test_db.flush()
    source = MemoryRecord(
        id=str(uuid4()),
        org_id=default_org_id,
        project_id=project.id,
        scope="project_shared",
        kind="fact",
        status="active",
        title="真实源标题不得导出",
        body_markdown="真实源正文不得出现在评测文件中。",
        retrieval_text=normalize_retrieval_text("真实源标题不得导出\n真实源正文不得出现在评测文件中。"),
        embedding_status="pending",
        origin="system",
        created_by_actor_type="system",
        created_by_actor_id="capture-test",
    )
    test_db.add(source)
    test_db.flush()
    source_id = f"real-chunk-{suffix}"
    source_link = MemoryEvidenceLink(
        memory_record_id=source.id,
        source_type="knowledge_chunk",
        source_id=source_id,
        evidence_role="supports",
        label="真实资料标签不得导出",
        locator_json={"chunk_index": 0},
    )
    test_db.add(source_link)
    test_db.flush()
    citation = MemoryCitation(
        source_type=source_link.source_type,
        source_id=source_link.source_id,
        label=source_link.label,
        locator_json=source_link.locator_json,
    )
    snapshot = memory_graph_source_snapshot_fingerprint(
        policy_version=_POLICY_VERSION,
        memory_record_id=source.id,
        title=source.title,
        body_markdown=source.body_markdown,
        citations=(citation,),
    )
    proposal = _proposal(source_id)
    proposal_record = MemoryRecord(
        id=str(uuid4()),
        org_id=default_org_id,
        project_id=project.id,
        scope="project_shared",
        kind="entity_note",
        status="active",
        title="审核后的图谱提案",
        body_markdown="已完成逐项审核。",
        structured_data_json={
            "memory_graph_proposal": proposal.model_dump(mode="json"),
            "source_memory_record_id": source.id,
            "graph_policy_version": _POLICY_VERSION,
        },
        content_fingerprint=snapshot,
        retrieval_text=normalize_retrieval_text("审核后的图谱提案"),
        embedding_status="pending",
        origin="system",
        created_by_actor_type="system",
        created_by_actor_id="capture-test",
    )
    test_db.add(proposal_record)
    test_db.flush()
    execution_run = ExecutionRun(
        id=str(uuid4()),
        project_id=project.id,
        run_type="memory_graph_extraction",
        status="succeeded",
        input_json={
            "memory_record_id": source.id,
            "source_snapshot_fingerprint": snapshot,
            "graph_policy_version": _POLICY_VERSION,
        },
        output_json={"proposal_memory_id": proposal_record.id},
    )
    test_db.add(execution_run)
    test_db.flush()
    test_db.add(
        RuntimeRun(
            id=str(uuid4()),
            kind="workflow_bridge",
            status="succeeded",
            org_id=default_org_id,
            user_id=default_user_id,
            project_id=project.id,
            execution_run_id=execution_run.id,
            engine="langgraph_workflow",
            trace_id=f"graph-capture-{suffix}",
            model=_MODEL,
            policy_snapshot_json={"approval_mode": "risky_only"},
        )
    )
    proposal_fingerprint = memory_graph_proposal_fingerprint(proposal)
    entities_by_local_id = {entity.local_id: entity.canonical_name for entity in proposal.entities}
    review_items = [
        (
            memory_graph_item_id(proposal_fingerprint, "entity", entity.semantic_key),
            "entity",
            "accepted",
        )
        for entity in proposal.entities
    ]
    review_items.append(
        (
            memory_graph_item_id(
                proposal_fingerprint,
                "relation",
                (
                    entities_by_local_id[proposal.relations[0].subject_local_id],
                    proposal.relations[0].predicate.value,
                    entities_by_local_id[proposal.relations[0].object_local_id],
                ),
            ),
            "relation",
            "rejected",
        )
    )
    test_db.add_all(
        [
            MemoryGraphReviewDecision(
                org_id=default_org_id,
                project_id=project.id,
                proposal_memory_record_id=proposal_record.id,
                item_id=item_id,
                item_type=item_type,
                proposal_fingerprint=proposal_fingerprint,
                decision=decision,
                reviewer_user_id=default_user_id,
            )
            for item_id, item_type, decision in review_items
        ]
    )
    test_db.commit()
    return {
        "proposal_memory_record_id": proposal_record.id,
        "source_memory_record_id": source.id,
        "execution_run_id": execution_run.id,
        "actual_source_id": source_id,
        "source_title": source.title,
        "source_body": source.body_markdown,
        "project_id": project.id,
    }


def _manifest(dataset: MemoryGraphBenchmarkDataset, records: dict[str, str]) -> MemoryGraphRuntimeCaptureManifest:
    return MemoryGraphRuntimeCaptureManifest(
        dataset_id=dataset.dataset_id,
        fixture_fingerprint=fixture_fingerprint(dataset),
        extractor_policy_version=_POLICY_VERSION,
        git_commit="a" * 40,
        provider="controlled-provider",
        model=_MODEL,
        provenance=EvaluationEvidenceProvenance(
            evidence_set_id="memory-graph-runtime-capture",
            capture_id="memory-graph-runtime-capture-1",
            capture_kind=EvaluationCaptureKind.CURRENT_PIPELINE,
            review_level=EvaluationReviewLevel.TWO_PERSON_REVIEW,
            evaluator_version="memory-graph-runtime-capture-v1",
            attestation_ref="ci:memory-graph-runtime-capture-1",
        ),
        captures=(
            MemoryGraphRuntimeCaptureItem(
                case_id="private-deployment",
                proposal_memory_record_id=records["proposal_memory_record_id"],
                source_memory_record_id=records["source_memory_record_id"],
                execution_run_id=records["execution_run_id"],
                evidence_map=(
                    MemoryGraphRuntimeEvidenceMap(
                        runtime_source_type="knowledge_chunk",
                        runtime_source_id=records["actual_source_id"],
                        benchmark_source_type="knowledge_chunk",
                        benchmark_source_id="benchmark-chunk",
                    ),
                ),
            ),
        ),
    )


def test_memory_graph_runtime_capture_redacts_durable_ids_and_source_content(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    dataset = _dataset()
    records = _seed_capture_records(test_db, default_org_id, default_user_id)

    captured = capture_memory_graph_runtime_run(test_db, dataset, _manifest(dataset, records))

    observation = captured.results[0]
    assert observation.org_id == "benchmark-org"
    assert observation.project_id == "benchmark-project"
    assert observation.memory_record_id == "benchmark-memory"
    assert observation.review_summary.accepted_item_count == 2
    assert observation.review_summary.rejected_item_count == 1
    assert observation.review_summary.pending_item_count == 0
    payload = observation.proposal_json
    assert isinstance(payload, dict)
    assert payload["entities"][0]["evidence_refs"][0]["source_id"] == "benchmark-chunk"
    serialized = captured.model_dump_json()
    for forbidden in records.values():
        assert forbidden not in serialized
    assert records["source_title"] not in serialized
    assert records["source_body"] not in serialized

    report = score_memory_graph_run(dataset, captured)
    assert report.capture_readiness.controlled_capture_ready is True


def test_memory_graph_runtime_capture_rejects_a_changed_source_snapshot(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    dataset = _dataset()
    records = _seed_capture_records(test_db, default_org_id, default_user_id)
    source = test_db.get(MemoryRecord, records["source_memory_record_id"])
    assert source is not None
    source.body_markdown = "该源知识已经被修改，旧提案不再可捕获。"
    test_db.commit()

    with pytest.raises(ValueError, match="source snapshot is stale"):
        capture_memory_graph_runtime_run(test_db, dataset, _manifest(dataset, records))


def test_memory_graph_runtime_capture_rejects_expired_proposals(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    dataset = _dataset()
    records = _seed_capture_records(test_db, default_org_id, default_user_id)
    proposal = test_db.get(MemoryRecord, records["proposal_memory_record_id"])
    assert proposal is not None
    proposal.expires_at = (datetime.now(UTC) - timedelta(seconds=1)).replace(tzinfo=None)
    test_db.commit()

    with pytest.raises(ValueError, match="proposal scope is invalid"):
        capture_memory_graph_runtime_run(test_db, dataset, _manifest(dataset, records))


def test_memory_graph_runtime_capture_rejects_failed_runtime_bridge(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    dataset = _dataset()
    records = _seed_capture_records(test_db, default_org_id, default_user_id)
    runtime_run = test_db.scalar(
        select(RuntimeRun).where(RuntimeRun.execution_run_id == records["execution_run_id"])
    )
    assert runtime_run is not None
    runtime_run.status = RuntimeRunStatus.FAILED.value
    test_db.commit()

    with pytest.raises(ValueError, match="runtime bridge scope is invalid"):
        capture_memory_graph_runtime_run(test_db, dataset, _manifest(dataset, records))
