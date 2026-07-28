"""Create the opt-in, user-owned first-run demo workspace."""

from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record_audit_event
from app.auth.schemas import CurrentUser
from app.auth.service import check_plan_limit
from app.models import (
    BidRequirementProfile,
    Bundle,
    Evidence,
    KnowledgeChunk,
    ParsedAsset,
    Project,
    ProjectMember,
    RequirementEvidenceLink,
    RequirementItem,
    SourceDocument,
)
from contracts.document_ingestion import DocumentIndexStatus, DocumentParseStatus

from .demo_data import (
    BUILTIN_DEMO_STORAGE_PREFIX,
    DEMO_BUNDLE_LABEL,
    DEMO_DOCUMENTS,
    DEMO_EVIDENCE,
    DEMO_PROJECT_NAME,
    DEMO_REQUIREMENTS,
)
from .schemas import ProjectCreate, ProjectRead
from .service import _create_project_with_defaults, _project_to_read


def create_demo_project_command(
    db: Session,
    current_user: CurrentUser,
) -> tuple[ProjectRead, bool]:
    """Return one deterministic demo workspace per user and active organization."""

    org_id = current_user.org_id or "default"
    existing = _find_active_demo_project(db, user_id=current_user.id, org_id=org_id)
    if existing is not None:
        return _project_to_read(existing), False

    check_plan_limit(
        db,
        current_user.id,
        "projects",
        delta=1,
        org_id=current_user.org_id,
    )

    project = _create_project_with_defaults(
        db,
        ProjectCreate(name=DEMO_PROJECT_NAME, scenario_package="bidpilot"),
        org_id,
        current_user.id,
    )
    bundle = Bundle(
        project_id=project.id,
        label=DEMO_BUNDLE_LABEL,
        source_type="builtin_demo",
        ingest_status="ingested",
    )
    db.add(bundle)
    db.flush()

    documents: dict[str, SourceDocument] = {}
    for document_definition in DEMO_DOCUMENTS:
        document = SourceDocument(
            bundle_id=bundle.id,
            storage_key=f"{BUILTIN_DEMO_STORAGE_PREFIX}{document_definition.key}",
            mime_type="text/markdown; charset=utf-8",
            checksum=hashlib.sha256(document_definition.content.encode("utf-8")).hexdigest(),
            original_filename=document_definition.filename,
            page_count=1,
            parse_status=DocumentParseStatus.PARSED.value,
            # The opt-in demo deliberately ships with deterministic sparse
            # retrieval only. It must not masquerade as a fully embedded live
            # upload while still remaining usable without any provider key.
            index_status=DocumentIndexStatus.DEGRADED.value,
            index_error_code="builtin_demo_sparse_only",
            version_number=1,
        )
        db.add(document)
        db.flush()
        documents[document_definition.key] = document
        db.add(
            ParsedAsset(
                source_document_id=document.id,
                parser_name="bidpilot_builtin_demo",
                parser_version="1",
                content_json={"text": document_definition.content, "source_kind": "builtin_demo"},
                layout_json={"format": "markdown", "source_kind": "builtin_demo"},
            )
        )
        db.add(
            KnowledgeChunk(
                project_id=project.id,
                source_document_id=document.id,
                chunk_index=0,
                chunk_key=hashlib.sha256(
                    f"{document.id}:{document.checksum}:0".encode("utf-8")
                ).hexdigest(),
                content=document_definition.content,
                metadata_json={
                    "source_kind": "builtin_demo",
                    "document_key": document_definition.key,
                    "locator": {
                        "source_document_id": document.id,
                        "chunk_index": 0,
                        "heading": None,
                        "table": None,
                        "text_anchor": document_definition.content[:240],
                        "source_checksum": document.checksum,
                        "document_version": document.version_number,
                    },
                },
                retrieval_text=document_definition.content,
                embedding_status="not_indexed",
            )
        )

    requirements: dict[str, RequirementItem] = {}
    for requirement_definition in DEMO_REQUIREMENTS:
        requirement = RequirementItem(
            project_id=project.id,
            section_key=requirement_definition.section_key,
            requirement_text=requirement_definition.text,
            original_text=requirement_definition.text,
            source_document_id=documents[requirement_definition.document_key].id,
            source_locator_json={
                "source_kind": "builtin_demo",
                "document": documents[requirement_definition.document_key].original_filename,
                "heading": requirement_definition.heading,
            },
            priority=requirement_definition.priority,
            status="confirmed",
            verification_status=requirement_definition.verification_status,
            extraction_confidence=1.0,
        )
        db.add(requirement)
        db.flush()
        requirements[requirement_definition.key] = requirement
        db.add(
            BidRequirementProfile(
                requirement_id=requirement.id,
                bid_category=requirement_definition.category,
                is_mandatory=requirement_definition.mandatory,
                score_weight=requirement_definition.score_weight,
                risk_level=requirement_definition.risk_level,
                coverage_status=requirement_definition.coverage_status,
                evidence_status=requirement_definition.evidence_status,
            )
        )

    for evidence_definition in DEMO_EVIDENCE:
        evidence = Evidence(
            project_id=project.id,
            source_document_id=documents[evidence_definition.document_key].id,
            quote_text=evidence_definition.quote,
            locator_json={
                "source_kind": "builtin_demo",
                "document": documents[evidence_definition.document_key].original_filename,
                "heading": evidence_definition.heading,
            },
            confidence=evidence_definition.confidence,
        )
        db.add(evidence)
        db.flush()
        for requirement_key in evidence_definition.requirement_keys:
            db.add(
                RequirementEvidenceLink(
                    requirement_id=requirements[requirement_key].id,
                    evidence_id=evidence.id,
                    relation_type="supports",
                    verification_status="verified",
                    created_by_user_id=current_user.id,
                )
            )

    record_audit_event(
        db,
        project_id=project.id,
        event_type="project.demo_seeded",
        actor_type="system",
        actor_id="builtin_demo",
        payload={
            "source_kind": "builtin_demo",
            "document_count": len(DEMO_DOCUMENTS),
            "requirement_count": len(DEMO_REQUIREMENTS),
            "evidence_count": len(DEMO_EVIDENCE),
        },
    )
    db.commit()
    db.refresh(project)
    return _project_to_read(project), True


def _find_active_demo_project(
    db: Session,
    *,
    user_id: str,
    org_id: str,
) -> Project | None:
    return db.scalar(
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(
            Project.org_id == org_id,
            Project.name == DEMO_PROJECT_NAME,
            Project.status != "deleted",
            ProjectMember.user_id == user_id,
            ProjectMember.role == "owner",
        )
        .order_by(Project.created_at.desc())
    )
