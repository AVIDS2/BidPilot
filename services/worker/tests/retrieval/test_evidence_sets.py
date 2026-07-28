from __future__ import annotations

from uuid import uuid4

import pytest

from app.db import SessionLocal
from app.models import (
    Bundle,
    EvidenceSet,
    ExecutionRun,
    KnowledgeChunk,
    Organization,
    Project,
    SourceDocument,
)
from app.retrieval.evidence_sets import (
    EvidenceSetScopeError,
    capture_evidence_set,
    load_authorized_evidence_set,
)
from contracts import CitationLocator, CitationValidationStatus, RetrievalCandidate


def _create_project_with_evidence(
    db,
    *,
    suffix: str,
    name: str,
) -> tuple[Project, SourceDocument, KnowledgeChunk, ExecutionRun]:
    organization = Organization(
        id=str(uuid4()),
        slug=f"evidence-{name}-{suffix}",
        name=f"Evidence {name}",
    )
    project = Project(
        id=str(uuid4()),
        org_id=organization.id,
        slug=f"evidence-project-{name}-{suffix}",
        name=f"Evidence Project {name}",
        scenario_package="bidpilot",
    )
    db.add_all((organization, project))
    db.flush()
    bundle = Bundle(project_id=project.id, label=f"Evidence {name}", source_type="upload")
    db.add(bundle)
    db.flush()
    source = SourceDocument(
        bundle_id=bundle.id,
        storage_key=f"tests/evidence-set-{name}-{suffix}.md",
        mime_type="text/markdown",
        checksum=(name[0] * 64),
        original_filename=f"evidence-{name}.md",
        page_count=4,
        version_number=1,
    )
    db.add(source)
    db.flush()
    chunk = KnowledgeChunk(
        project_id=project.id,
        source_document_id=source.id,
        chunk_index=0,
        content=f"{name} 项目的投标技术方案必须包含部署和验收计划。",
        metadata_json={
            "source_document_id": source.id,
            "document_version": source.version_number,
            "document_checksum": source.checksum,
        },
    )
    run = ExecutionRun(
        id=str(uuid4()),
        project_id=project.id,
        run_type="draft_section",
        status="running",
    )
    db.add_all((chunk, run))
    db.flush()
    return project, source, chunk, run


def _candidate(
    *,
    project_id: str,
    source: SourceDocument,
    chunk: KnowledgeChunk,
    chunk_index: int | None = None,
    text_anchor: str | None = None,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=chunk.id,
        project_id=project_id,
        source_document_id=source.id,
        content=chunk.content,
        locator=CitationLocator(
            source_document_id=source.id,
            chunk_index=chunk.chunk_index if chunk_index is None else chunk_index,
            page=1,
            text_anchor=text_anchor,
            validation_status=CitationValidationStatus.VERIFIED,
        ),
        dense_rank=1,
        sparse_rank=1,
        fused_rank=1,
        final_score=0.9,
        methods=("dense", "fts"),
    )


def test_capture_evidence_set_persists_scope_checked_snapshot_and_reuses_it() -> None:
    suffix = uuid4().hex[:8]
    db = SessionLocal()
    try:
        project, source, chunk, run = _create_project_with_evidence(
            db,
            suffix=suffix,
            name="valid",
        )
        db.commit()

        first = capture_evidence_set(
            db,
            project_id=project.id,
            execution_run_id=run.id,
            section_key="technical-approach",
            query_text="技术方案",
            retrieval_profile_id="test-profile",
            degraded_reasons=(),
            candidates=(
                _candidate(
                    project_id=project.id,
                    source=source,
                    chunk=chunk,
                    text_anchor="部署和验收计划",
                ),
            ),
        )
        db.commit()

        assert first.status == "ready"
        assert len(first.items) == 1
        item = first.items[0]
        assert item.chunk_id == chunk.id
        assert item.source_document_id == source.id
        assert item.source_document_version == 1
        assert item.source_document_checksum == source.checksum
        assert item.locator_json["chunk_index"] == chunk.chunk_index

        replay = capture_evidence_set(
            db,
            project_id=project.id,
            execution_run_id=run.id,
            section_key="technical-approach",
            query_text="ignored on replay",
            retrieval_profile_id=None,
            degraded_reasons=("ignored_on_replay",),
            candidates=(),
        )
        assert replay.id == first.id
        assert len(replay.items) == 1
        assert db.get(EvidenceSet, first.id) is not None
        with pytest.raises(EvidenceSetScopeError, match="execution_run_scope_invalid"):
            load_authorized_evidence_set(
                db,
                evidence_set_id=first.id,
                project_id=project.id,
                execution_run_id=str(uuid4()),
            )
    finally:
        db.rollback()
        db.close()


def test_capture_evidence_set_rejects_cross_project_chunk_even_when_candidate_claims_target_scope() -> None:
    suffix = uuid4().hex[:8]
    db = SessionLocal()
    try:
        target_project, _, _, target_run = _create_project_with_evidence(
            db,
            suffix=suffix,
            name="target",
        )
        _, foreign_source, foreign_chunk, _ = _create_project_with_evidence(
            db,
            suffix=suffix,
            name="foreign",
        )
        db.commit()

        snapshot = capture_evidence_set(
            db,
            project_id=target_project.id,
            execution_run_id=target_run.id,
            section_key="technical-approach",
            query_text="技术方案",
            retrieval_profile_id=None,
            degraded_reasons=(),
            candidates=(
                _candidate(
                    project_id=target_project.id,
                    source=foreign_source,
                    chunk=foreign_chunk,
                ),
            ),
        )
        db.commit()

        assert snapshot.status == "missing_evidence"
        assert not snapshot.items
        assert "cross_project_evidence" in snapshot.rejected_reasons
    finally:
        db.rollback()
        db.close()


def test_capture_evidence_set_rejects_invalid_locator() -> None:
    suffix = uuid4().hex[:8]
    db = SessionLocal()
    try:
        project, source, chunk, run = _create_project_with_evidence(
            db,
            suffix=suffix,
            name="locator",
        )
        db.commit()

        snapshot = capture_evidence_set(
            db,
            project_id=project.id,
            execution_run_id=run.id,
            section_key="technical-approach",
            query_text="技术方案",
            retrieval_profile_id=None,
            degraded_reasons=(),
            candidates=(
                _candidate(
                    project_id=project.id,
                    source=source,
                    chunk=chunk,
                    chunk_index=99,
                ),
            ),
        )
        db.commit()

        assert snapshot.status == "missing_evidence"
        assert not snapshot.items
        assert "locator_chunk_index_mismatch" in snapshot.rejected_reasons
    finally:
        db.rollback()
        db.close()


def test_authorized_evidence_set_invalidates_when_source_document_is_replaced() -> None:
    suffix = uuid4().hex[:8]
    db = SessionLocal()
    try:
        project, source, chunk, run = _create_project_with_evidence(
            db,
            suffix=suffix,
            name="superseded",
        )
        db.commit()
        captured = capture_evidence_set(
            db,
            project_id=project.id,
            execution_run_id=run.id,
            section_key="technical-approach",
            query_text="技术方案",
            retrieval_profile_id=None,
            degraded_reasons=(),
            candidates=(
                _candidate(
                    project_id=project.id,
                    source=source,
                    chunk=chunk,
                ),
            ),
        )
        db.commit()

        replacement = SourceDocument(
            bundle_id=source.bundle_id,
            storage_key=f"tests/evidence-set-replacement-{suffix}.md",
            mime_type="text/markdown",
            checksum="r" * 64,
            original_filename=source.original_filename,
            version_number=2,
            supersedes_document_id=source.id,
        )
        db.add(replacement)
        db.commit()

        refreshed = load_authorized_evidence_set(
            db,
            evidence_set_id=captured.id,
            project_id=project.id,
        )
        db.commit()

        assert refreshed.status == "invalidated"
        assert not refreshed.items
        assert "source_document_superseded" in refreshed.rejected_reasons
    finally:
        db.rollback()
        db.close()
