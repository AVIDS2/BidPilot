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
    for definition in DEMO_DOCUMENTS:
        document = SourceDocument(
            bundle_id=bundle.id,
            storage_key=f"{BUILTIN_DEMO_STORAGE_PREFIX}{definition.key}",
            mime_type="text/markdown; charset=utf-8",
            checksum=hashlib.sha256(definition.content.encode("utf-8")).hexdigest(),
            original_filename=definition.filename,
            page_count=1,
            parse_status="completed",
        )
        db.add(document)
        db.flush()
        documents[definition.key] = document
        db.add(
            ParsedAsset(
                source_document_id=document.id,
                parser_name="bidpilot_builtin_demo",
                parser_version="1",
                content_json={"text": definition.content, "source_kind": "builtin_demo"},
                layout_json={"format": "markdown", "source_kind": "builtin_demo"},
            )
        )
        db.add(
            KnowledgeChunk(
                project_id=project.id,
                source_document_id=document.id,
                chunk_index=0,
                content=definition.content,
                metadata_json={"source_kind": "builtin_demo", "document_key": definition.key},
                retrieval_text=definition.content,
                embedding_status="not_indexed",
            )
        )

    requirements: dict[str, RequirementItem] = {}
    for definition in DEMO_REQUIREMENTS:
        requirement = RequirementItem(
            project_id=project.id,
            section_key=definition.section_key,
            requirement_text=definition.text,
            original_text=definition.text,
            source_document_id=documents[definition.document_key].id,
            source_locator_json={
                "source_kind": "builtin_demo",
                "document": documents[definition.document_key].original_filename,
                "heading": definition.heading,
            },
            priority=definition.priority,
            status="confirmed",
            verification_status=definition.verification_status,
            extraction_confidence=1.0,
        )
        db.add(requirement)
        db.flush()
        requirements[definition.key] = requirement
        db.add(
            BidRequirementProfile(
                requirement_id=requirement.id,
                bid_category=definition.category,
                is_mandatory=definition.mandatory,
                score_weight=definition.score_weight,
                risk_level=definition.risk_level,
                coverage_status=definition.coverage_status,
                evidence_status=definition.evidence_status,
            )
        )

    for definition in DEMO_EVIDENCE:
        evidence = Evidence(
            project_id=project.id,
            source_document_id=documents[definition.document_key].id,
            quote_text=definition.quote,
            locator_json={
                "source_kind": "builtin_demo",
                "document": documents[definition.document_key].original_filename,
                "heading": definition.heading,
            },
            confidence=definition.confidence,
        )
        db.add(evidence)
        db.flush()
        for requirement_key in definition.requirement_keys:
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
