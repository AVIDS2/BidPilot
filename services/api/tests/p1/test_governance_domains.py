"""P1 governance domain invariants without external providers or queues."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.schemas import CurrentUser
from app.changes.schemas import (
    DocumentChangeImpactUpdate,
    DocumentChangeSetCreate,
)
from app.changes.service import (
    analyze_document_change_set_command,
    create_document_change_set_command,
    update_document_change_impact_command,
)
from app.collaboration.service import get_collaboration_board_query
from app.content_library.schemas import (
    ContentLibraryEntryCreate,
    ContentLibraryPublish,
    ContentLibraryUsageCreate,
)
from app.content_library.service import (
    apply_content_library_entry_command,
    create_content_library_entry_command,
    publish_content_library_entry_command,
)
from app.db import Base
from app.models import (
    AuditEvent,
    Bundle,
    Organization,
    OrganizationMembership,
    ParsedAsset,
    Project,
    ProjectMember,
    SourceDocument,
    User,
)
from app.opportunities.schemas import (
    OpportunityAssessmentDecisionCreate,
    OpportunityAssessmentUpsert,
)
from app.opportunities.service import (
    decide_opportunity_command,
    upsert_opportunity_assessment_command,
)


def _make_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _make_context(SessionLocal):
    db = SessionLocal()
    org = Organization(slug=f"p1-{uuid.uuid4().hex[:8]}", name="P1 Org")
    db.add(org)
    db.flush()
    user = User(
        email=f"p1-{uuid.uuid4().hex[:8]}@example.test",
        display_name="P1 Manager",
        password_hash="not-used-in-service-tests",
        role="admin",
        email_verified=True,
        org_id=org.id,
    )
    db.add(user)
    db.flush()
    db.add(OrganizationMembership(org_id=org.id, user_id=user.id, role="owner"))
    project = Project(
        org_id=org.id,
        slug=f"p1-project-{uuid.uuid4().hex[:8]}",
        name="P1 Project",
        scenario_package="bidpilot",
    )
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role="manager"))
    db.commit()
    return db, project, CurrentUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role="admin",
        plan="starter",
        org_id=org.id,
        org_slug=org.slug,
        email_verified=True,
        disabled=False,
    )


def test_go_no_go_is_versioned_and_rejects_stale_updates() -> None:
    SessionLocal = _make_db()
    db, project, user = _make_context(SessionLocal)
    try:
        assessment = upsert_opportunity_assessment_command(
            db,
            project_id=project.id,
            payload=OpportunityAssessmentUpsert(
                status="ready",
                scorecard_json={"fit": 8},
                rationale="Existing implementation evidence is sufficient.",
            ),
            current_user=user,
        )
        decided = decide_opportunity_command(
            db,
            project_id=project.id,
            payload=OpportunityAssessmentDecisionCreate(
                decision="conditional_go",
                rationale="Proceed after commercial review.",
                lock_version=assessment.lock_version,
            ),
            current_user=user,
        )

        assert decided.status == "decided"
        assert decided.decision == "conditional_go"
        assert [item.sequence for item in decided.decisions] == [1]

        with pytest.raises(HTTPException) as exc:
            upsert_opportunity_assessment_command(
                db,
                project_id=project.id,
                payload=OpportunityAssessmentUpsert(
                    status="ready",
                    lock_version=assessment.lock_version,
                ),
                current_user=user,
            )
        assert exc.value.status_code == 409
    finally:
        db.close()


def test_content_library_reuses_an_approved_immutable_version_only() -> None:
    SessionLocal = _make_db()
    db, project, user = _make_context(SessionLocal)
    try:
        entry = create_content_library_entry_command(
            db,
            payload=ContentLibraryEntryCreate(
                title="Delivery approach",
                category="technical",
                content_markdown="## Delivery\n\nA governed response.",
                source_json={"evidence": ["case-study-1"]},
            ),
            current_user=user,
        )
        with pytest.raises(HTTPException) as exc:
            apply_content_library_entry_command(
                db,
                entry_id=entry.id,
                payload=ContentLibraryUsageCreate(project_id=project.id),
                current_user=user,
            )
        assert exc.value.status_code == 409

        published = publish_content_library_entry_command(
            db,
            entry_id=entry.id,
            payload=ContentLibraryPublish(),
            current_user=user,
        )
        usage = apply_content_library_entry_command(
            db,
            entry_id=published.id,
            payload=ContentLibraryUsageCreate(project_id=project.id, usage_purpose="draft_context"),
            current_user=user,
        )

        assert published.lifecycle_status == "published"
        assert published.review_status == "approved"
        assert usage.content_version_id == published.latest_version.id
        assert db.scalar(select(AuditEvent).where(AuditEvent.event_type == "content_library.applied")) is not None
    finally:
        db.close()


def test_document_change_is_analyzed_then_impact_is_audited() -> None:
    SessionLocal = _make_db()
    db, project, user = _make_context(SessionLocal)
    try:
        bundle = Bundle(project_id=project.id, label="RFP", source_type="upload")
        db.add(bundle)
        db.flush()
        previous = SourceDocument(
            bundle_id=bundle.id,
            storage_key="private/rfp-v1.txt",
            mime_type="text/plain",
            checksum="a" * 64,
            original_filename="rfp-v1.txt",
            parse_status="parsed",
        )
        db.add(previous)
        db.flush()
        replacement = SourceDocument(
            bundle_id=bundle.id,
            storage_key="private/rfp-v2.txt",
            mime_type="text/plain",
            checksum="b" * 64,
            original_filename="rfp-v2.txt",
            supersedes_document_id=previous.id,
            version_number=2,
            parse_status="parsed",
        )
        db.add(replacement)
        db.flush()
        db.add_all(
            [
                ParsedAsset(
                    source_document_id=previous.id,
                    parser_name="docpilot_parser",
                    parser_version="3.1",
                    content_json={"normalized_text": "# Scope\n\nProvide support during business hours."},
                ),
                ParsedAsset(
                    source_document_id=replacement.id,
                    parser_name="docpilot_parser",
                    parser_version="3.1",
                    content_json={"normalized_text": "# Scope\n\nProvide 24/7 support and an incident response plan."},
                ),
            ]
        )
        db.commit()

        created = create_document_change_set_command(
            db,
            project_id=project.id,
            payload=DocumentChangeSetCreate(replacement_document_id=replacement.id),
            current_user=user,
        )
        analyzed = analyze_document_change_set_command(db, change_set_id=created.id, current_user=user)
        impact = analyzed.impacts[0]
        resolved = update_document_change_impact_command(
            db,
            change_set_id=analyzed.id,
            impact_id=impact.id,
            payload=DocumentChangeImpactUpdate(status="resolved"),
            current_user=user,
        )

        assert analyzed.status == "analyzed"
        assert analyzed.summary_json["analysis_status"] == "complete"
        assert resolved.status == "resolved"
        audit_types = set(db.scalars(select(AuditEvent.event_type)).all())
        assert {"document_change.created", "document_change.analyzed", "document_change.impact_updated"} <= audit_types
    finally:
        db.close()


def test_collaboration_board_reads_assignments_and_active_runs_from_project_truth() -> None:
    SessionLocal = _make_db()
    db, project, user = _make_context(SessionLocal)
    try:
        board = get_collaboration_board_query(db, project_id=project.id, current_user=user)

        assert board.project_id == project.id
        assert [(member.user_id, member.role) for member in board.members] == [(user.id, "manager")]
        assert board.requirement_items == []
        assert board.active_workflow_count == 0
    finally:
        db.close()
