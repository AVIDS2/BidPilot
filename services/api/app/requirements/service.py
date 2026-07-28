from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.exc import StaleDataError

from app.access.service import ROLE_CAPABILITIES, require_project_capability
from app.audit.service import record_audit_event
from app.auth.schemas import CurrentUser
from app.projects.repository import get_project_member
from app.models import (
    BidRequirementProfile,
    Claim,
    ClaimEvidenceLink,
    RequirementClaimLink,
    RequirementDecision,
    RequirementEvidenceLink,
    RequirementItem,
)

from .repository import (
    create_requirement,
    get_existing_requirement_evidence_link,
    get_evidence_for_project,
    get_requirement_decision,
    get_requirement_evidence_link,
    get_requirement_claim,
    get_requirement_for_org,
    get_source_document_for_project,
    get_user_for_org,
    list_requirements_by_project,
    update_requirement,
)
from .schemas import (
    BidRequirementProfileRead,
    ClaimReviewQueueItemRead,
    ClaimReviewQueueRead,
    RequirementDetailRead,
    RequirementBulkAssign,
    RequirementClaimCreate,
    RequirementClaimRead,
    RequirementDecisionCreate,
    RequirementDecisionRead,
    RequirementEvidenceLinkCreate,
    RequirementEvidenceLinkRead,
    RequirementEvidenceLinkUpdate,
    RequirementItemCreate,
    RequirementItemRead,
    RequirementItemUpdate,
)


def _organization_id(current_user: CurrentUser) -> str:
    return current_user.org_id or "default"


def _get_requirement_for_user(
    db: Session,
    requirement_id: str,
    current_user: CurrentUser,
) -> RequirementItem:
    item = get_requirement_for_org(db, requirement_id, _organization_id(current_user))
    if item is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return item


def _require_requirement_capability(
    db: Session,
    item: RequirementItem,
    current_user: CurrentUser,
    capability: str,
) -> RequirementItem:
    require_project_capability(
        db,
        current_user=current_user,
        project_id=item.project_id,
        capability=capability,
    )
    return item


def create_requirement_command(
    db: Session,
    payload: RequirementItemCreate,
    *,
    current_user: CurrentUser,
    actor_id: str,
) -> RequirementItemRead:
    access = require_project_capability(
        db,
        current_user=current_user,
        project_id=payload.project_id,
        capability="requirements.write",
    )
    org_id = access.project.org_id
    if payload.owner_user_id is not None or payload.reviewer_user_id is not None:
        require_project_capability(
            db,
            current_user=current_user,
            project_id=payload.project_id,
            capability="requirements.assign",
        )
    _validate_source_document(db, payload.source_document_id, payload.project_id)
    _validate_assignee(
        db,
        payload.owner_user_id,
        project_id=payload.project_id,
        org_id=org_id,
        label="Owner",
        required_capability="requirements.write",
    )
    _validate_assignee(
        db,
        payload.reviewer_user_id,
        project_id=payload.project_id,
        org_id=org_id,
        label="Reviewer",
        required_capability="requirements.review",
    )

    item = RequirementItem(
        project_id=payload.project_id,
        section_key=payload.section_key,
        requirement_text=payload.requirement_text,
        original_text=payload.original_text,
        source_document_id=payload.source_document_id,
        source_locator_json=payload.source_locator_json,
        priority=payload.priority,
        status="untriaged",
        owner_user_id=payload.owner_user_id,
        reviewer_user_id=payload.reviewer_user_id,
        due_at=payload.due_at,
        extraction_confidence=payload.extraction_confidence,
    )
    # A requirement without a profile cannot participate in readiness, evidence
    # coverage, or risk queries. Every ledger row starts with an explicit
    # uncovered/missing baseline and can then be enriched by the caller.
    item.bid_profile = BidRequirementProfile(
        **(payload.bid_profile.model_dump() if payload.bid_profile is not None else {})
    )
    create_requirement(db, item)
    record_audit_event(
        db,
        project_id=item.project_id,
        event_type="requirement.created",
        actor_type="user",
        actor_id=actor_id,
        payload={"requirement_id": item.id},
    )
    db.commit()
    db.refresh(item)
    return _to_read(item)


def list_requirements_query(
    db: Session,
    project_id: str,
    *,
    current_user: CurrentUser,
    bid_category: str | None = None,
    coverage_status: str | None = None,
    evidence_status: str | None = None,
    risk_level: str | None = None,
    owner_user_id: str | None = None,
    verification_status: str | None = None,
) -> list[RequirementItemRead]:
    access = require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.read",
    )
    items = list_requirements_by_project(
        db,
        project_id,
        access.project.org_id,
        bid_category=bid_category,
        coverage_status=coverage_status,
        evidence_status=evidence_status,
        risk_level=risk_level,
        owner_user_id=owner_user_id,
        verification_status=verification_status,
    )
    return [_to_read(item) for item in items]


def get_claim_review_queue_query(
    db: Session,
    project_id: str,
    *,
    current_user: CurrentUser,
    limit: int = 100,
) -> ClaimReviewQueueRead:
    """Return AI-created draft claims that still need a human decision.

    This query intentionally returns no claim text. The queue is a control-plane
    view: reviewers can see whether evidence is ready before opening the
    requirement ledger, while the assistant transport stays free of draft prose.
    """

    require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.read",
    )
    bounded_limit = min(max(limit, 1), 100)
    claims = list(
        db.scalars(
            select(Claim)
            .options(
                selectinload(Claim.evidence_links),
                selectinload(Claim.requirement_links)
                .selectinload(RequirementClaimLink.requirement)
                .selectinload(RequirementItem.evidence_links),
            )
            .where(
                Claim.project_id == project_id,
                Claim.status == "draft",
                Claim.created_by_actor == "ai",
            )
            .order_by(Claim.created_at.asc(), Claim.id.asc())
            .limit(bounded_limit + 1)
        ).all()
    )
    truncated = len(claims) > bounded_limit
    if truncated:
        claims = claims[:bounded_limit]

    items = [_claim_review_queue_item(claim) for claim in claims]
    return ClaimReviewQueueRead(
        project_id=project_id,
        count=len(items),
        ready_to_verify_count=sum(item.ready_to_verify for item in items),
        blocked_by_evidence_count=sum(not item.ready_to_verify for item in items),
        items=items,
        truncated=truncated,
    )


def get_requirement_query(
    db: Session,
    requirement_id: str,
    *,
    current_user: CurrentUser,
) -> RequirementDetailRead:
    item = _get_requirement_for_user(db, requirement_id, current_user)
    _require_requirement_capability(db, item, current_user, "project.read")
    return _to_detail(item)


def update_requirement_command(
    db: Session,
    requirement_id: str,
    payload: RequirementItemUpdate,
    *,
    current_user: CurrentUser,
    actor_id: str,
) -> RequirementItemRead:
    item = _get_requirement_for_user(db, requirement_id, current_user)
    changed_fields = payload.model_fields_set - {"lock_version", "bid_profile"}
    assignment_fields = {"owner_user_id", "reviewer_user_id"}
    has_assignment_change = bool(changed_fields & assignment_fields)
    has_review_change = "verification_status" in changed_fields
    has_regular_change = bool(changed_fields - assignment_fields - {"verification_status"}) or payload.bid_profile is not None
    if has_regular_change or not (has_assignment_change or has_review_change):
        _require_requirement_capability(db, item, current_user, "requirements.write")
    if has_assignment_change:
        _require_requirement_capability(db, item, current_user, "requirements.assign")
    if has_review_change:
        _require_requirement_capability(db, item, current_user, "requirements.review")
    if payload.lock_version is not None and payload.lock_version != item.lock_version:
        raise HTTPException(status_code=409, detail="Requirement changed; refresh and retry")

    org_id = _organization_id(current_user)
    _validate_source_document(db, payload.source_document_id, item.project_id)
    _validate_assignee(
        db,
        payload.owner_user_id,
        project_id=item.project_id,
        org_id=org_id,
        label="Owner",
        required_capability="requirements.write",
    )
    _validate_assignee(
        db,
        payload.reviewer_user_id,
        project_id=item.project_id,
        org_id=org_id,
        label="Reviewer",
        required_capability="requirements.review",
    )

    for field in changed_fields:
        setattr(item, field, getattr(payload, field))
    if payload.bid_profile is not None:
        if item.bid_profile is None:
            item.bid_profile = BidRequirementProfile(requirement_id=item.id)
        for field in payload.bid_profile.model_fields_set:
            setattr(item.bid_profile, field, getattr(payload.bid_profile, field))
        _touch_requirement(item)

    try:
        update_requirement(db, item)
        record_audit_event(
            db,
            project_id=item.project_id,
            event_type="requirement.updated",
            actor_type="user",
            actor_id=actor_id,
            payload={
                "requirement_id": item.id,
                "fields": sorted(payload.model_fields_set - {"lock_version"}),
            },
        )
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Requirement changed; refresh and retry") from exc
    db.refresh(item)
    return _to_read(item)


def bulk_assign_requirements_command(
    db: Session,
    payload: RequirementBulkAssign,
    *,
    current_user: CurrentUser,
    actor_id: str,
) -> list[RequirementItemRead]:
    org_id = _organization_id(current_user)
    items: list[RequirementItem] = []
    missing_requirement_ids: list[str] = []
    conflicting_requirement_ids: list[str] = []
    for requirement_id in payload.requirement_ids:
        item = get_requirement_for_org(db, requirement_id, org_id)
        if item is None:
            missing_requirement_ids.append(requirement_id)
            continue
        if payload.lock_versions[requirement_id] != item.lock_version:
            conflicting_requirement_ids.append(requirement_id)
        items.append(item)

    if missing_requirement_ids:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "requirements_not_found",
                "requirement_ids": missing_requirement_ids,
            },
        )
    if conflicting_requirement_ids:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "requirements_changed",
                "requirement_ids": conflicting_requirement_ids,
            },
        )

    project_ids = {item.project_id for item in items}
    for project_id in project_ids:
        require_project_capability(
            db,
            current_user=current_user,
            project_id=project_id,
            capability="requirements.assign",
        )
        _validate_assignee(
            db,
            payload.owner_user_id,
            project_id=project_id,
            org_id=org_id,
            label="Owner",
            required_capability="requirements.write",
        )
        _validate_assignee(
            db,
            payload.reviewer_user_id,
            project_id=project_id,
            org_id=org_id,
            label="Reviewer",
            required_capability="requirements.review",
        )

    for item in items:
        if "owner_user_id" in payload.model_fields_set:
            item.owner_user_id = payload.owner_user_id
            if payload.owner_user_id is not None and item.status == "untriaged":
                item.status = "assigned"
            elif payload.owner_user_id is None and item.status == "assigned":
                item.status = "untriaged"
        if "reviewer_user_id" in payload.model_fields_set:
            item.reviewer_user_id = payload.reviewer_user_id

    try:
        for project_id in {item.project_id for item in items}:
            record_audit_event(
                db,
                project_id=project_id,
                event_type="requirement.bulk_assigned",
                actor_type="user",
                actor_id=actor_id,
                payload={
                    "requirement_ids": [
                        item.id for item in items if item.project_id == project_id
                    ],
                    **(
                        {"owner_user_id": payload.owner_user_id}
                        if "owner_user_id" in payload.model_fields_set
                        else {}
                    ),
                    **(
                        {"reviewer_user_id": payload.reviewer_user_id}
                        if "reviewer_user_id" in payload.model_fields_set
                        else {}
                    ),
                },
            )
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "requirements_changed",
                "requirement_ids": payload.requirement_ids,
            },
        ) from exc
    return [_to_read(item) for item in items]


def link_evidence_command(
    db: Session,
    requirement_id: str,
    payload: RequirementEvidenceLinkCreate,
    *,
    current_user: CurrentUser,
    actor_id: str,
) -> RequirementEvidenceLinkRead:
    item = _get_requirement_for_user(db, requirement_id, current_user)
    _require_requirement_capability(db, item, current_user, "requirements.write")
    evidence = get_evidence_for_project(db, payload.evidence_id, item.project_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    existing = get_existing_requirement_evidence_link(
        db,
        item.id,
        evidence.id,
        payload.relation_type,
    )
    if existing is not None:
        existing.evidence = evidence
        return _evidence_link_to_read(existing)

    link = RequirementEvidenceLink(
        requirement_id=item.id,
        evidence_id=evidence.id,
        relation_type=payload.relation_type,
        created_by_user_id=actor_id,
        evidence=evidence,
    )
    item.evidence_links.append(link)
    _ensure_bid_profile(item)
    _recompute_bid_profile(item)
    _touch_requirement(item)
    record_audit_event(
        db,
        project_id=item.project_id,
        event_type="requirement.evidence_linked",
        actor_type="user",
        actor_id=actor_id,
        payload={
            "requirement_id": item.id,
            "evidence_id": evidence.id,
            "relation_type": payload.relation_type,
        },
    )
    db.commit()
    return _evidence_link_to_read(link)


def update_evidence_link_command(
    db: Session,
    requirement_id: str,
    link_id: str,
    payload: RequirementEvidenceLinkUpdate,
    *,
    current_user: CurrentUser,
    actor_id: str,
) -> RequirementEvidenceLinkRead:
    item = _get_requirement_for_user(db, requirement_id, current_user)
    _require_requirement_capability(db, item, current_user, "requirements.review")
    link = get_requirement_evidence_link(db, link_id, item.id)
    if link is None:
        raise HTTPException(status_code=404, detail="Evidence link not found")
    link.verification_status = payload.verification_status
    _ensure_bid_profile(item)
    _recompute_bid_profile(item)
    _touch_requirement(item)
    record_audit_event(
        db,
        project_id=item.project_id,
        event_type="requirement.evidence_verified",
        actor_type="user",
        actor_id=actor_id,
        payload={
            "requirement_id": item.id,
            "link_id": link.id,
            "verification_status": link.verification_status,
        },
    )
    db.commit()
    link.evidence = get_evidence_for_project(db, link.evidence_id, item.project_id)
    return _evidence_link_to_read(link)


def create_requirement_decision_command(
    db: Session,
    requirement_id: str,
    payload: RequirementDecisionCreate,
    *,
    current_user: CurrentUser,
    actor_id: str,
) -> RequirementDecisionRead:
    if payload.decision_type not in {"not_applicable", "accepted_risk", "waiver"}:
        raise HTTPException(status_code=400, detail="Unsupported decision type")
    item = _get_requirement_for_user(db, requirement_id, current_user)
    _require_requirement_capability(db, item, current_user, "requirements.write")
    decision = RequirementDecision(
        requirement_id=item.id,
        decision_type=payload.decision_type,
        rationale=payload.rationale,
        requested_by_user_id=actor_id,
    )
    item.decisions.append(decision)
    _touch_requirement(item)
    record_audit_event(
        db,
        project_id=item.project_id,
        event_type="requirement.decision_requested",
        actor_type="user",
        actor_id=actor_id,
        payload={
            "requirement_id": item.id,
            "decision_type": decision.decision_type,
        },
    )
    db.commit()
    return RequirementDecisionRead.model_validate(decision)


def approve_requirement_decision_command(
    db: Session,
    requirement_id: str,
    decision_id: str,
    *,
    current_user: CurrentUser,
    actor_id: str,
) -> RequirementDecisionRead:
    item = _get_requirement_for_user(db, requirement_id, current_user)
    _require_requirement_capability(db, item, current_user, "requirements.review")
    decision = get_requirement_decision(db, decision_id, item.id)
    if decision is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    if decision.status != "pending":
        raise HTTPException(status_code=409, detail="Decision is already resolved")
    decision.status = "approved"
    decision.approved_by_user_id = actor_id
    decision.resolved_at = datetime.now(UTC).replace(tzinfo=None)
    _ensure_bid_profile(item)
    _recompute_bid_profile(item)
    _touch_requirement(item)
    record_audit_event(
        db,
        project_id=item.project_id,
        event_type="requirement.decision_approved",
        actor_type="user",
        actor_id=actor_id,
        payload={
            "requirement_id": item.id,
            "decision_id": decision.id,
            "decision_type": decision.decision_type,
        },
    )
    db.commit()
    return RequirementDecisionRead.model_validate(decision)


def create_requirement_claim_command(
    db: Session,
    requirement_id: str,
    payload: RequirementClaimCreate,
    *,
    current_user: CurrentUser,
    actor_id: str,
) -> RequirementClaimRead:
    item = _get_requirement_for_user(db, requirement_id, current_user)
    _require_requirement_capability(db, item, current_user, "requirements.write")
    linked_evidence_ids = {
        link.evidence_id
        for link in item.evidence_links
        if link.relation_type == "supports"
    }
    requested_evidence_ids = set(payload.evidence_ids)
    if not requested_evidence_ids.issubset(linked_evidence_ids):
        raise HTTPException(
            status_code=400,
            detail="Claim evidence must be linked to this requirement first",
        )

    claim = Claim(
        project_id=item.project_id,
        claim_text=payload.claim_text,
        claim_type=payload.claim_type,
        created_by_actor="user",
        created_by_user_id=actor_id,
    )
    requirement_link = RequirementClaimLink(
        requirement_id=item.id,
        claim=claim,
        coverage_role=payload.coverage_role,
    )
    for evidence_id in payload.evidence_ids:
        claim.evidence_links.append(
            ClaimEvidenceLink(
                evidence_id=evidence_id,
                relation_type="supports",
            )
        )
    item.claim_links.append(requirement_link)
    _touch_requirement(item)
    db.flush()
    record_audit_event(
        db,
        project_id=item.project_id,
        event_type="requirement.claim_created",
        actor_type="user",
        actor_id=actor_id,
        payload={
            "requirement_id": item.id,
            "claim_id": claim.id,
            "evidence_ids": payload.evidence_ids,
        },
    )
    db.commit()
    return _claim_to_read(requirement_link)


def verify_requirement_claim_command(
    db: Session,
    requirement_id: str,
    claim_id: str,
    *,
    current_user: CurrentUser,
    actor_id: str,
) -> RequirementClaimRead:
    item = _get_requirement_for_user(db, requirement_id, current_user)
    _require_requirement_capability(db, item, current_user, "requirements.review")
    claim = get_requirement_claim(db, claim_id, item.id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.status == "verified":
        raise HTTPException(status_code=409, detail="Claim is already verified")
    if claim.claim_type == "factual" and not claim.evidence_links:
        raise HTTPException(status_code=409, detail="Factual claim requires verified evidence")

    linked_requirement_ids = {link.requirement_id for link in claim.requirement_links}
    claim_evidence_ids = {link.evidence_id for link in claim.evidence_links}
    if not linked_requirement_ids:
        raise HTTPException(status_code=409, detail="Claim has no linked requirements")

    expected_requirement_evidence_pairs = {
        (requirement_id, evidence_id)
        for requirement_id in linked_requirement_ids
        for evidence_id in claim_evidence_ids
    }
    verified_requirement_evidence_pairs = set(
        db.execute(
            select(
                RequirementEvidenceLink.requirement_id,
                RequirementEvidenceLink.evidence_id,
            ).where(
                RequirementEvidenceLink.requirement_id.in_(linked_requirement_ids),
                RequirementEvidenceLink.evidence_id.in_(claim_evidence_ids),
                RequirementEvidenceLink.relation_type == "supports",
                RequirementEvidenceLink.verification_status == "verified",
            )
        ).all()
    )
    if claim.claim_type == "factual" and not expected_requirement_evidence_pairs.issubset(
        verified_requirement_evidence_pairs
    ):
        raise HTTPException(
            status_code=409,
            detail="Claim evidence must be verified for every linked requirement first",
        )

    linked_requirements = list(
        db.scalars(
            select(RequirementItem)
            .options(
                selectinload(RequirementItem.bid_profile),
                selectinload(RequirementItem.evidence_links),
                selectinload(RequirementItem.claim_links)
                .selectinload(RequirementClaimLink.claim)
                .selectinload(Claim.evidence_links),
                selectinload(RequirementItem.decisions),
            )
            .where(RequirementItem.id.in_(linked_requirement_ids))
        ).all()
    )
    if (
        len(linked_requirements) != len(linked_requirement_ids)
        or any(requirement.project_id != item.project_id for requirement in linked_requirements)
    ):
        raise HTTPException(status_code=409, detail="Claim has invalid linked requirement scope")

    claim.status = "verified"
    for link in claim.evidence_links:
        link.verification_status = "verified"
    for linked_requirement in linked_requirements:
        _recompute_bid_profile(linked_requirement)
        _touch_requirement(linked_requirement)
    record_audit_event(
        db,
        project_id=item.project_id,
        event_type="requirement.claim_verified",
        actor_type="user",
        actor_id=actor_id,
        payload={
            "requirement_id": item.id,
            "claim_id": claim.id,
            "linked_requirement_count": len(linked_requirement_ids),
        },
    )
    db.commit()
    requirement_link = next(link for link in item.claim_links if link.claim_id == claim.id)
    return _claim_to_read(requirement_link)


def _to_read(item: RequirementItem) -> RequirementItemRead:
    profile = (
        BidRequirementProfileRead.model_validate(item.bid_profile)
        if item.bid_profile is not None
        else None
    )
    return RequirementItemRead(
        id=item.id,
        project_id=item.project_id,
        section_key=item.section_key,
        requirement_text=item.requirement_text,
        original_text=item.original_text,
        source_document_id=item.source_document_id,
        source_document_name=(
            item.source_document.original_filename
            if item.source_document is not None
            else None
        ),
        source_locator_json=item.source_locator_json,
        priority=item.priority,
        status=item.status,
        owner_user_id=item.owner_user_id,
        reviewer_user_id=item.reviewer_user_id,
        due_at=item.due_at,
        verification_status=item.verification_status,
        extraction_confidence=item.extraction_confidence,
        lock_version=item.lock_version,
        updated_at=item.updated_at,
        bid_profile=profile,
    )


def _to_detail(item: RequirementItem) -> RequirementDetailRead:
    base = _to_read(item).model_dump()
    evidence_links = [
        RequirementEvidenceLinkRead(
            id=link.id,
            requirement_id=link.requirement_id,
            evidence_id=link.evidence_id,
            relation_type=link.relation_type,
            verification_status=link.verification_status,
            quote_text=link.evidence.quote_text,
            source_document_id=link.evidence.source_document_id,
            source_document_name=(
                link.evidence.source_document.original_filename
                if link.evidence.source_document is not None
                else None
            ),
            locator_json=link.evidence.locator_json,
            confidence=link.evidence.confidence,
            created_at=link.created_at,
        )
        for link in item.evidence_links
    ]
    return RequirementDetailRead(
        **base,
        evidence_links=evidence_links,
        claims=[_claim_to_read(link) for link in item.claim_links],
        decisions=item.decisions,
    )


def _evidence_link_to_read(link: RequirementEvidenceLink) -> RequirementEvidenceLinkRead:
    return RequirementEvidenceLinkRead(
        id=link.id,
        requirement_id=link.requirement_id,
        evidence_id=link.evidence_id,
        relation_type=link.relation_type,
        verification_status=link.verification_status,
        quote_text=link.evidence.quote_text,
        source_document_id=link.evidence.source_document_id,
        source_document_name=(
            link.evidence.source_document.original_filename
            if link.evidence.source_document is not None
            else None
        ),
        locator_json=link.evidence.locator_json,
        confidence=link.evidence.confidence,
        created_at=link.created_at,
    )


def _claim_to_read(link: RequirementClaimLink) -> RequirementClaimRead:
    claim = link.claim
    return RequirementClaimRead(
        id=claim.id,
        project_id=claim.project_id,
        requirement_id=link.requirement_id,
        claim_text=claim.claim_text,
        claim_type=claim.claim_type,
        status=claim.status,
        coverage_role=link.coverage_role,
        section_version_id=claim.section_version_id,
        generation_run_id=claim.generation_run_id,
        created_by_actor=claim.created_by_actor,
        created_by_user_id=claim.created_by_user_id,
        evidence_ids=[evidence_link.evidence_id for evidence_link in claim.evidence_links],
        created_at=claim.created_at,
        updated_at=claim.updated_at,
    )


def _claim_review_queue_item(claim: Claim) -> ClaimReviewQueueItemRead:
    requirement_ids = {link.requirement_id for link in claim.requirement_links}
    evidence_ids = {link.evidence_id for link in claim.evidence_links}
    expected_pairs = {
        (requirement_id, evidence_id)
        for requirement_id in requirement_ids
        for evidence_id in evidence_ids
    }
    verified_pairs = {
        (requirement_link.requirement_id, evidence_link.evidence_id)
        for requirement_link in claim.requirement_links
        for evidence_link in requirement_link.requirement.evidence_links
        if evidence_link.relation_type == "supports"
        and evidence_link.verification_status == "verified"
        and evidence_link.evidence_id in evidence_ids
    }

    if claim.claim_type == "inference":
        ready_to_verify = bool(requirement_ids)
        blocked_evidence_count = 0
    elif claim.claim_type == "factual":
        missing_pairs = expected_pairs - verified_pairs
        ready_to_verify = bool(requirement_ids) and bool(evidence_ids) and not missing_pairs
        blocked_evidence_count = len(missing_pairs) if evidence_ids else 1
    else:
        ready_to_verify = False
        blocked_evidence_count = 1

    return ClaimReviewQueueItemRead(
        id=claim.id,
        claim_type=claim.claim_type,
        status=claim.status,
        created_by_actor=claim.created_by_actor,
        section_version_id=claim.section_version_id,
        requirement_ids=sorted(requirement_ids),
        evidence_count=len(evidence_ids),
        blocked_evidence_count=blocked_evidence_count,
        ready_to_verify=ready_to_verify,
    )


def _ensure_bid_profile(item: RequirementItem) -> BidRequirementProfile:
    if item.bid_profile is None:
        item.bid_profile = BidRequirementProfile(requirement_id=item.id)
    return item.bid_profile


def _touch_requirement(item: RequirementItem) -> None:
    """Advance the aggregate version when a child record changes its ledger state."""
    item.updated_at = datetime.now(UTC).replace(tzinfo=None)


def _recompute_bid_profile(item: RequirementItem) -> None:
    profile = _ensure_bid_profile(item)
    approved_decisions = [decision for decision in item.decisions if decision.status == "approved"]
    if any(decision.decision_type == "not_applicable" for decision in approved_decisions):
        profile.coverage_status = "not_applicable"
        profile.evidence_status = "not_required"
        return
    if any(decision.decision_type in {"accepted_risk", "waiver"} for decision in approved_decisions):
        profile.coverage_status = "accepted_risk"
        if profile.evidence_status == "missing":
            profile.evidence_status = "not_required"
        return

    verified_conflicts = [
        link
        for link in item.evidence_links
        if link.relation_type == "contradicts" and link.verification_status == "verified"
    ]
    if verified_conflicts:
        profile.coverage_status = "disputed"
        profile.evidence_status = "conflicting"
        return

    support_links = [link for link in item.evidence_links if link.relation_type == "supports"]
    verified_support = [link for link in support_links if link.verification_status == "verified"]
    if verified_support:
        verified_claims = [
            link.claim
            for link in item.claim_links
            if link.claim.status == "verified"
            and link.claim.claim_type == "factual"
            and any(
                evidence_link.verification_status == "verified"
                for evidence_link in link.claim.evidence_links
            )
        ]
        profile.coverage_status = "covered" if verified_claims else "partial"
        profile.evidence_status = "sufficient"
    elif support_links:
        profile.coverage_status = "partial"
        profile.evidence_status = "weak"
    else:
        profile.coverage_status = "uncovered"
        profile.evidence_status = "missing"


def _validate_source_document(
    db: Session,
    source_document_id: str | None,
    project_id: str,
) -> None:
    if source_document_id and get_source_document_for_project(db, source_document_id, project_id) is None:
        raise HTTPException(status_code=400, detail="Source document is not in this project")


def _validate_assignee(
    db: Session,
    user_id: str | None,
    *,
    project_id: str,
    org_id: str,
    label: str,
    required_capability: str,
) -> None:
    if user_id is None:
        return

    user = get_user_for_org(db, user_id, org_id)
    if user is None:
        raise HTTPException(status_code=400, detail=f"{label} is not an active organization member")
    if user.role == "admin":
        return

    membership = get_project_member(db, project_id, user.id)
    if membership is None:
        raise HTTPException(status_code=400, detail=f"{label} is not a project member")
    if required_capability not in ROLE_CAPABILITIES.get(membership.role, frozenset()):
        raise HTTPException(
            status_code=400,
            detail=f"{label} does not have the required project capability",
        )
