from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.access.service import require_project_capability
from app.auth.schemas import CurrentUser
from app.models import (
    Deliverable,
    DeliverableSection,
    ExecutionRun,
    ProjectMember,
    RequirementItem,
    ReviewThread,
)

from .schemas import (
    CollaborationBoardRead,
    CollaborationMemberRead,
    CollaborationRequirementRead,
)


TERMINAL_REQUIREMENT_STATUSES = {"covered", "waived", "not_applicable"}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def get_collaboration_board_query(
    db: Session,
    *,
    project_id: str,
    current_user: CurrentUser,
    limit: int = 250,
) -> CollaborationBoardRead:
    require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.read",
    )
    bounded_limit = min(max(limit, 1), 500)
    members = list(
        db.scalars(
            select(ProjectMember)
            .options(selectinload(ProjectMember.user))
            .where(ProjectMember.project_id == project_id)
            .order_by(ProjectMember.created_at, ProjectMember.user_id)
        ).all()
    )
    display_names = {member.user_id: member.user.display_name for member in members if member.user is not None}
    requirements = list(
        db.scalars(
            select(RequirementItem)
            .options(selectinload(RequirementItem.bid_profile))
            .where(RequirementItem.project_id == project_id)
            .order_by(RequirementItem.due_at.is_(None), RequirementItem.due_at, RequirementItem.id)
            .limit(bounded_limit)
        ).all()
    )
    now = _now()
    requirement_items: list[CollaborationRequirementRead] = []
    for requirement in requirements:
        needs_assignment = requirement.owner_user_id is None or requirement.reviewer_user_id is None
        overdue = bool(
            requirement.due_at
            and requirement.due_at < now
            and requirement.status not in TERMINAL_REQUIREMENT_STATUSES
        )
        profile = requirement.bid_profile
        requirement_items.append(
            CollaborationRequirementRead(
                requirement_id=requirement.id,
                section_key=requirement.section_key,
                requirement_text=requirement.requirement_text,
                status=requirement.status,
                priority=requirement.priority,
                verification_status=requirement.verification_status,
                owner_user_id=requirement.owner_user_id,
                owner_display_name=display_names.get(requirement.owner_user_id or ""),
                reviewer_user_id=requirement.reviewer_user_id,
                reviewer_display_name=display_names.get(requirement.reviewer_user_id or ""),
                due_at=requirement.due_at,
                overdue=overdue,
                needs_assignment=needs_assignment,
                risk_level=profile.risk_level if profile else None,
                coverage_status=profile.coverage_status if profile else None,
            )
        )

    open_review_thread_count = int(
        db.scalar(
            select(func.count(ReviewThread.id))
            .join(DeliverableSection, DeliverableSection.id == ReviewThread.deliverable_section_id)
            .join(Deliverable, Deliverable.id == DeliverableSection.deliverable_id)
            .where(Deliverable.project_id == project_id, ReviewThread.status == "open")
        )
        or 0
    )
    active_workflow_count = int(
        db.scalar(
            select(func.count(ExecutionRun.id)).where(
                ExecutionRun.project_id == project_id,
                ExecutionRun.status.in_(("queued", "running", "awaiting_human")),
            )
        )
        or 0
    )
    return CollaborationBoardRead(
        project_id=project_id,
        members=[
            CollaborationMemberRead(
                user_id=member.user_id,
                display_name=member.user.display_name if member.user is not None else member.user_id,
                role=member.role,
            )
            for member in members
        ],
        requirement_items=requirement_items,
        unassigned_requirement_count=sum(item.needs_assignment for item in requirement_items),
        overdue_requirement_count=sum(item.overdue for item in requirement_items),
        review_required_count=sum(
            item.verification_status != "verified" and item.status not in TERMINAL_REQUIREMENT_STATUSES
            for item in requirement_items
        ),
        open_review_thread_count=open_review_thread_count,
        active_workflow_count=active_workflow_count,
    )
