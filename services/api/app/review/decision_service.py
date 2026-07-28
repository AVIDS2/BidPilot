"""Durable review decisions shared by review and LangGraph resume commands."""

from __future__ import annotations

from typing import Final, Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record_audit_event
from app.auth.schemas import CurrentUser
from app.models import (
    Deliverable,
    DeliverableSection,
    ReviewComment,
    ReviewThread,
    SectionVersion,
)

from .repository import create_review_thread


CanonicalReviewDecision = Literal["approved", "rejected"]


CANONICAL_DECISIONS: Final[dict[str, CanonicalReviewDecision]] = {
    "approve": "approved",
    "approved": "approved",
    "reject": "rejected",
    "rejected": "rejected",
    "needs_revision": "rejected",
}


def canonical_review_decision(value: str) -> CanonicalReviewDecision:
    try:
        return CANONICAL_DECISIONS[value]
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported review decision.",
        ) from exc


def resolve_review_version(
    db: Session,
    *,
    section: DeliverableSection,
    section_version_id: str,
) -> SectionVersion:
    """Resolve the immutable version that a human is reviewing."""
    version = db.get(SectionVersion, section_version_id)
    if version is None or version.deliverable_section_id != section.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_section_version",
                "message": "The selected section version does not belong to this section.",
            },
        )
    return version


def recompute_deliverable_status(db: Session, deliverable: Deliverable) -> None:
    """Reflect review progress without making an unapproved draft exportable."""
    sections = list(
        db.scalars(
            select(DeliverableSection).where(DeliverableSection.deliverable_id == deliverable.id)
        ).all()
    )
    versioned_sections = [
        section
        for section in sections
        if db.scalar(
            select(SectionVersion.id)
            .where(SectionVersion.deliverable_section_id == section.id)
            .limit(1)
        )
        is not None
    ]
    if not versioned_sections:
        deliverable.status = "draft"
    elif all(
        section.status == "approved" and section.approved_version_id is not None
        for section in versioned_sections
    ):
        deliverable.status = "approved"
    elif any(
        section.approved_version_id is not None or section.status == "in_review"
        for section in versioned_sections
    ):
        deliverable.status = "in_review"
    else:
        deliverable.status = "draft"


def _review_thread_for_version(db: Session, section_version_id: str) -> ReviewThread | None:
    return db.scalar(
        select(ReviewThread)
        .where(ReviewThread.section_version_id == section_version_id)
        .order_by(ReviewThread.id.desc())
        .limit(1)
    )


def apply_review_decision(
    db: Session,
    *,
    section: DeliverableSection,
    version: SectionVersion,
    decision: str,
    current_user: CurrentUser,
    comment: str | None,
) -> tuple[ReviewThread, Deliverable, bool]:
    """Apply a decision to one immutable candidate without committing it.

    Rejecting a newer candidate intentionally preserves any earlier approved
    snapshot, so export cannot regress to a mutable or unreviewed version.
    """
    deliverable = db.get(Deliverable, section.deliverable_id)
    if deliverable is None:
        raise RuntimeError(f"Deliverable {section.deliverable_id} not found")

    existing_thread = _review_thread_for_version(db, version.id)
    if existing_thread is not None and existing_thread.status != "open":
        if existing_thread.status == decision:
            # Browser retries may replay the same human decision. Preserve the
            # original audit/comment/outbox trail instead of appending another.
            return existing_thread, deliverable, False
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "review_decision_already_finalized",
                "message": "This review candidate already has a final decision.",
            },
        )

    was_deliverable_approved = deliverable.status == "approved"
    if decision == "approved":
        section.status = "approved"
        section.approved_version_id = version.id
    else:
        if section.approved_version_id == version.id:
            section.approved_version_id = None
        section.status = "approved" if section.approved_version_id else "rejected"

    thread = existing_thread
    if thread is None:
        thread = create_review_thread(
            db,
            ReviewThread(
                deliverable_section_id=section.id,
                section_version_id=version.id,
                status=decision,
                opened_by=current_user.id,
                resolved_by=current_user.id,
            ),
        )
    else:
        thread.status = decision
        thread.resolved_by = current_user.id

    if comment:
        db.add(
            ReviewComment(
                review_thread_id=thread.id,
                author_type="human",
                author_id=current_user.id,
                body=comment,
            )
        )

    db.flush()
    record_audit_event(
        db,
        project_id=deliverable.project_id,
        event_type=f"review.{decision}",
        actor_type="user",
        actor_id=current_user.id,
        payload={
            "section_id": section.id,
            "section_key": section.section_key,
            "section_version_id": version.id,
            "version_number": version.version_number,
            "comment": comment,
        },
    )
    recompute_deliverable_status(db, deliverable)
    if deliverable.status == "approved" and not was_deliverable_approved:
        record_audit_event(
            db,
            project_id=deliverable.project_id,
            event_type="deliverable.approved",
            actor_type="user",
            actor_id=current_user.id,
            payload={"deliverable_id": deliverable.id},
        )
    return thread, deliverable, True
