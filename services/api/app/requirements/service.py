from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.audit.service import record_audit_event
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
    get_project_for_org,
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


def create_requirement_command(
    db: Session,
    payload: RequirementItemCreate,
    *,
    org_id: str,
    actor_id: str,
) -> RequirementItemRead:
    project = get_project_for_org(db, payload.project_id, org_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    _validate_source_document(db, payload.source_document_id, payload.project_id)
    _validate_assignee(db, payload.owner_user_id, org_id, "Owner")
    _validate_assignee(db, payload.reviewer_user_id, org_id, "Reviewer")

    item = RequirementItem(
        project_id=payload.project_id,
        section_key=payload.section_key,
        requirement_text=payload.requirement_text,
        original_text=payload.original_text,
        source_document_id=payload.source_document_id,
        source_locator_json=payload.source_locator_json,
        priority=payload.priority,
        owner_user_id=payload.owner_user_id,
        reviewer_user_id=payload.reviewer_user_id,
        due_at=payload.due_at,
        extraction_confidence=payload.extraction_confidence,
    )
    if payload.bid_profile is not None:
        item.bid_profile = BidRequirementProfile(**payload.bid_profile.model_dump())
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
    org_id: str,
    bid_category: str | None = None,
    coverage_status: str | None = None,
    evidence_status: str | None = None,
    risk_level: str | None = None,
    owner_user_id: str | None = None,
    verification_status: str | None = None,
) -> list[RequirementItemRead]:
    if get_project_for_org(db, project_id, org_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    items = list_requirements_by_project(
        db,
        project_id,
        org_id,
        bid_category=bid_category,
        coverage_status=coverage_status,
        evidence_status=evidence_status,
        risk_level=risk_level,
        owner_user_id=owner_user_id,
        verification_status=verification_status,
    )
    return [_to_read(item) for item in items]


def get_requirement_query(
    db: Session,
    requirement_id: str,
    *,
    org_id: str,
) -> RequirementDetailRead:
    item = get_requirement_for_org(db, requirement_id, org_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return _to_detail(item)


def update_requirement_command(
    db: Session,
    requirement_id: str,
    payload: RequirementItemUpdate,
    *,
    org_id: str,
    actor_id: str,
) -> RequirementItemRead:
    item = get_requirement_for_org(db, requirement_id, org_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    if payload.lock_version is not None and payload.lock_version != item.lock_version:
        raise HTTPException(status_code=409, detail="Requirement changed; refresh and retry")

    _validate_source_document(db, payload.source_document_id, item.project_id)
    _validate_assignee(db, payload.owner_user_id, org_id, "Owner")
    _validate_assignee(db, payload.reviewer_user_id, org_id, "Reviewer")

    changed_fields = payload.model_fields_set - {"lock_version", "bid_profile"}
    for field in changed_fields:
        setattr(item, field, getattr(payload, field))
    if payload.bid_profile is not None:
        if item.bid_profile is None:
            item.bid_profile = BidRequirementProfile(requirement_id=item.id)
        for field in payload.bid_profile.model_fields_set:
            setattr(item.bid_profile, field, getattr(payload.bid_profile, field))

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
    org_id: str,
    actor_id: str,
) -> list[RequirementItemRead]:
    _validate_assignee(db, payload.owner_user_id, org_id, "Owner")
    _validate_assignee(db, payload.reviewer_user_id, org_id, "Reviewer")
    items: list[RequirementItem] = []
    for requirement_id in payload.requirement_ids:
        item = get_requirement_for_org(db, requirement_id, org_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Requirement not found")
        if payload.lock_versions[requirement_id] != item.lock_version:
            raise HTTPException(status_code=409, detail="Requirement changed; refresh and retry")
        if "owner_user_id" in payload.model_fields_set:
            item.owner_user_id = payload.owner_user_id
        if "reviewer_user_id" in payload.model_fields_set:
            item.reviewer_user_id = payload.reviewer_user_id
        items.append(item)

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
                    "owner_user_id": payload.owner_user_id,
                    "reviewer_user_id": payload.reviewer_user_id,
                },
            )
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Requirement changed; refresh and retry") from exc
    return [_to_read(item) for item in items]


def link_evidence_command(
    db: Session,
    requirement_id: str,
    payload: RequirementEvidenceLinkCreate,
    *,
    org_id: str,
    actor_id: str,
) -> RequirementEvidenceLinkRead:
    item = get_requirement_for_org(db, requirement_id, org_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
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
    org_id: str,
    actor_id: str,
) -> RequirementEvidenceLinkRead:
    item = get_requirement_for_org(db, requirement_id, org_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    link = get_requirement_evidence_link(db, link_id, item.id)
    if link is None:
        raise HTTPException(status_code=404, detail="Evidence link not found")
    link.verification_status = payload.verification_status
    _ensure_bid_profile(item)
    _recompute_bid_profile(item)
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
    org_id: str,
    actor_id: str,
) -> RequirementDecisionRead:
    if payload.decision_type not in {"not_applicable", "accepted_risk", "waiver"}:
        raise HTTPException(status_code=400, detail="Unsupported decision type")
    item = get_requirement_for_org(db, requirement_id, org_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    decision = RequirementDecision(
        requirement_id=item.id,
        decision_type=payload.decision_type,
        rationale=payload.rationale,
        requested_by_user_id=actor_id,
    )
    item.decisions.append(decision)
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
    org_id: str,
    actor_id: str,
    actor_role: str,
) -> RequirementDecisionRead:
    item = get_requirement_for_org(db, requirement_id, org_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    if actor_role != "admin" and item.reviewer_user_id != actor_id:
        raise HTTPException(status_code=403, detail="Reviewer or admin approval required")
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
    org_id: str,
    actor_id: str,
) -> RequirementClaimRead:
    item = get_requirement_for_org(db, requirement_id, org_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
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
    org_id: str,
    actor_id: str,
    actor_role: str,
) -> RequirementClaimRead:
    item = get_requirement_for_org(db, requirement_id, org_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Requirement not found")
    if actor_role != "admin" and item.reviewer_user_id != actor_id:
        raise HTTPException(status_code=403, detail="Reviewer or admin verification required")
    claim = get_requirement_claim(db, claim_id, item.id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.status == "verified":
        raise HTTPException(status_code=409, detail="Claim is already verified")
    if claim.claim_type == "factual" and not claim.evidence_links:
        raise HTTPException(status_code=409, detail="Factual claim requires verified evidence")

    verified_requirement_evidence = {
        link.evidence_id
        for link in item.evidence_links
        if link.relation_type == "supports" and link.verification_status == "verified"
    }
    claim_evidence_ids = {link.evidence_id for link in claim.evidence_links}
    if claim.claim_type == "factual" and not claim_evidence_ids.issubset(
        verified_requirement_evidence
    ):
        raise HTTPException(status_code=409, detail="Claim evidence must be verified first")

    claim.status = "verified"
    for link in claim.evidence_links:
        link.verification_status = "verified"
    _recompute_bid_profile(item)
    record_audit_event(
        db,
        project_id=item.project_id,
        event_type="requirement.claim_verified",
        actor_type="user",
        actor_id=actor_id,
        payload={"requirement_id": item.id, "claim_id": claim.id},
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


def _ensure_bid_profile(item: RequirementItem) -> BidRequirementProfile:
    if item.bid_profile is None:
        item.bid_profile = BidRequirementProfile(requirement_id=item.id)
    return item.bid_profile


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
    org_id: str,
    label: str,
) -> None:
    if user_id and get_user_for_org(db, user_id, org_id) is None:
        raise HTTPException(status_code=400, detail=f"{label} is not in this organization")
