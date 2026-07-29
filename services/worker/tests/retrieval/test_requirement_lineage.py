import uuid

from sqlalchemy import select

from app.execution import ingest
from app.graph.nodes import rfp_parser
from app.db import SessionLocal
from app.models import (
    Bundle,
    KnowledgeChunk,
    Organization,
    Project,
    RequirementItem,
    SourceDocument,
)


def _create_source_chunk() -> tuple[str, str, str]:
    suffix = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        organization = Organization(
            id=str(uuid.uuid4()),
            slug=f"requirement-lineage-{suffix}",
            name="Requirement Lineage",
        )
        project = Project(
            id=str(uuid.uuid4()),
            org_id=organization.id,
            slug=f"requirement-lineage-{suffix}",
            name="Requirement Lineage",
            scenario_package="bidpilot",
        )
        bundle = Bundle(
            id=str(uuid.uuid4()),
            project_id=project.id,
            label="Tender requirements",
            source_type="upload",
        )
        document = SourceDocument(
            id=str(uuid.uuid4()),
            bundle_id=bundle.id,
            storage_key=f"tests/{suffix}.txt",
            mime_type="text/plain",
            checksum=(suffix * 8)[:64],
            original_filename="requirements.txt",
            parse_status="parsed",
            version_number=1,
        )
        chunk = KnowledgeChunk(
            id=str(uuid.uuid4()),
            project_id=project.id,
            source_document_id=document.id,
            chunk_index=0,
            chunk_key=f"chunk-{suffix}",
            content="投标人必须提供项目实施方案，并说明交付计划和风险控制措施。",
            metadata_json={
                "chunk_key": f"chunk-{suffix}",
                "locator": {
                    "heading": "技术要求",
                    "page": 3,
                    "text_anchor": "投标人必须提供项目实施方案",
                },
            },
        )
        db.add(organization)
        db.commit()
        db.add(project)
        db.commit()
        db.add(bundle)
        db.commit()
        db.add(document)
        db.commit()
        db.add(chunk)
        db.commit()
        return bundle.id, project.id, document.id
    finally:
        db.close()


def test_ingest_requirement_extraction_is_source_aware_and_idempotent() -> None:
    bundle_id, project_id, source_document_id = _create_source_chunk()

    assert ingest._extract_and_store_requirements(
        bundle_id,
        source_document_ids={source_document_id},
    ) == 1

    db = SessionLocal()
    try:
        item = db.scalar(
            select(RequirementItem).where(RequirementItem.project_id == project_id)
        )
        assert item is not None
        assert item.source_document_id == source_document_id
        assert item.original_text == item.requirement_text
        assert item.extraction_key is not None
        assert item.status == "untriaged"
        assert item.source_locator_json is not None
        assert item.source_locator_json["document_version"] == 1
        assert item.source_locator_json["locator"]["page"] == 3
        assert item.bid_profile is not None
        assert item.bid_profile.coverage_status == "uncovered"
        assert item.bid_profile.evidence_status == "missing"
        item.requirement_text = "人工修订后的实施方案要求。"
        db.commit()
    finally:
        db.close()

    # Same immutable document version must not create a duplicate or overwrite
    # the reviewer's edit when a task is redelivered.
    assert ingest._extract_and_store_requirements(
        bundle_id,
        source_document_ids={source_document_id},
    ) == 0

    db = SessionLocal()
    try:
        items = list(
            db.scalars(
                select(RequirementItem).where(RequirementItem.project_id == project_id)
            ).all()
        )
        assert len(items) == 1
        assert items[0].requirement_text == "人工修订后的实施方案要求。"
    finally:
        db.close()


def test_supplier_evidence_bundle_never_materializes_requirement_rows() -> None:
    bundle_id, project_id, source_document_id = _create_source_chunk()

    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        assert bundle is not None
        bundle.source_type = "supplier_evidence"
        db.commit()
    finally:
        db.close()

    assert ingest._extract_and_store_requirements(
        bundle_id,
        source_document_ids={source_document_id},
    ) == 0

    db = SessionLocal()
    try:
        assert (
            db.scalar(
                select(RequirementItem).where(RequirementItem.project_id == project_id)
            )
            is None
        )
    finally:
        db.close()


def test_workflow_requirement_parser_never_materializes_source_less_ledger_rows() -> None:
    bundle_id, project_id, source_document_id = _create_source_chunk()
    del bundle_id
    requirement_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(
            RequirementItem(
                id=requirement_id,
                project_id=project_id,
                section_key="extracted",
                requirement_text="投标人必须提供项目实施方案，并说明交付计划和风险控制措施。",
                source_document_id=source_document_id,
                status="untriaged",
            )
        )
        db.commit()
    finally:
        db.close()

    resolved = rfp_parser._persist_requirements(
        project_id,
        [
            {
                "section_key": "extracted",
                "requirement_text": "投标人必须提供项目实施方案，并说明交付计划和风险控制措施。",
                "priority": "high",
            },
            {
                "section_key": "model-only",
                "requirement_text": "模型提出的补充建议不应作为来源事实。",
                "priority": "normal",
            },
        ],
    )

    assert resolved[0]["id"] == requirement_id
    assert "id" not in resolved[1]
    db = SessionLocal()
    try:
        assert (
            db.scalar(
                select(RequirementItem).where(RequirementItem.project_id == project_id)
            )
            is not None
        )
        assert len(
            list(
                db.scalars(
                    select(RequirementItem).where(RequirementItem.project_id == project_id)
                ).all()
            )
        ) == 1
    finally:
        db.close()
