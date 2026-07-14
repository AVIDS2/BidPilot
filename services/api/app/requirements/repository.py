from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    BidRequirementProfile,
    Evidence,
    Claim,
    ClaimEvidenceLink,
    Project,
    RequirementDecision,
    RequirementClaimLink,
    RequirementEvidenceLink,
    RequirementItem,
    SourceDocument,
    Bundle,
    User,
)


def get_project_for_org(db: Session, project_id: str, org_id: str) -> Project | None:
    return db.scalar(select(Project).where(Project.id == project_id, Project.org_id == org_id))


def create_requirement(db: Session, item: RequirementItem) -> RequirementItem:
    db.add(item)
    db.flush()
    return item


def list_requirements_by_project(
    db: Session,
    project_id: str,
    org_id: str,
    *,
    bid_category: str | None = None,
    coverage_status: str | None = None,
    evidence_status: str | None = None,
    risk_level: str | None = None,
    owner_user_id: str | None = None,
    verification_status: str | None = None,
) -> list[RequirementItem]:
    stmt = (
        select(RequirementItem)
        .join(Project, Project.id == RequirementItem.project_id)
        .outerjoin(BidRequirementProfile, BidRequirementProfile.requirement_id == RequirementItem.id)
        .options(selectinload(RequirementItem.bid_profile))
        .where(RequirementItem.project_id == project_id, Project.org_id == org_id)
    )
    if bid_category:
        stmt = stmt.where(BidRequirementProfile.bid_category == bid_category)
    if coverage_status:
        stmt = stmt.where(BidRequirementProfile.coverage_status == coverage_status)
    if evidence_status:
        stmt = stmt.where(BidRequirementProfile.evidence_status == evidence_status)
    if risk_level:
        stmt = stmt.where(BidRequirementProfile.risk_level == risk_level)
    if owner_user_id:
        stmt = stmt.where(RequirementItem.owner_user_id == owner_user_id)
    if verification_status:
        stmt = stmt.where(RequirementItem.verification_status == verification_status)
    stmt = stmt.order_by(RequirementItem.section_key, RequirementItem.priority, RequirementItem.id)
    return list(db.scalars(stmt).all())


def get_requirement_for_org(
    db: Session,
    requirement_id: str,
    org_id: str,
) -> RequirementItem | None:
    stmt = (
        select(RequirementItem)
        .join(Project, Project.id == RequirementItem.project_id)
        .options(
            selectinload(RequirementItem.bid_profile),
            selectinload(RequirementItem.evidence_links).selectinload(
                RequirementEvidenceLink.evidence
            ),
            selectinload(RequirementItem.claim_links)
            .selectinload(RequirementClaimLink.claim)
            .selectinload(Claim.evidence_links),
            selectinload(RequirementItem.decisions),
        )
        .where(RequirementItem.id == requirement_id, Project.org_id == org_id)
    )
    return db.scalar(stmt)


def get_user_for_org(db: Session, user_id: str, org_id: str) -> User | None:
    return db.scalar(select(User).where(User.id == user_id, User.org_id == org_id))


def get_source_document_for_project(
    db: Session,
    source_document_id: str,
    project_id: str,
) -> SourceDocument | None:
    stmt = (
        select(SourceDocument)
        .join(Bundle, Bundle.id == SourceDocument.bundle_id)
        .where(SourceDocument.id == source_document_id, Bundle.project_id == project_id)
    )
    return db.scalar(stmt)


def get_evidence_for_project(db: Session, evidence_id: str, project_id: str) -> Evidence | None:
    return db.scalar(
        select(Evidence).where(Evidence.id == evidence_id, Evidence.project_id == project_id)
    )


def get_requirement_evidence_link(
    db: Session,
    link_id: str,
    requirement_id: str,
) -> RequirementEvidenceLink | None:
    return db.scalar(
        select(RequirementEvidenceLink).where(
            RequirementEvidenceLink.id == link_id,
            RequirementEvidenceLink.requirement_id == requirement_id,
        )
    )


def get_existing_requirement_evidence_link(
    db: Session,
    requirement_id: str,
    evidence_id: str,
    relation_type: str,
) -> RequirementEvidenceLink | None:
    return db.scalar(
        select(RequirementEvidenceLink).where(
            RequirementEvidenceLink.requirement_id == requirement_id,
            RequirementEvidenceLink.evidence_id == evidence_id,
            RequirementEvidenceLink.relation_type == relation_type,
        )
    )


def get_requirement_decision(
    db: Session,
    decision_id: str,
    requirement_id: str,
) -> RequirementDecision | None:
    return db.scalar(
        select(RequirementDecision).where(
            RequirementDecision.id == decision_id,
            RequirementDecision.requirement_id == requirement_id,
        )
    )


def get_requirement_claim(
    db: Session,
    claim_id: str,
    requirement_id: str,
) -> Claim | None:
    stmt = (
        select(Claim)
        .join(RequirementClaimLink, RequirementClaimLink.claim_id == Claim.id)
        .options(selectinload(Claim.evidence_links))
        .where(
            Claim.id == claim_id,
            RequirementClaimLink.requirement_id == requirement_id,
        )
    )
    return db.scalar(stmt)


def get_claim_evidence_links(db: Session, claim_id: str) -> list[ClaimEvidenceLink]:
    return list(
        db.scalars(
            select(ClaimEvidenceLink).where(ClaimEvidenceLink.claim_id == claim_id)
        ).all()
    )


def update_requirement(db: Session, item: RequirementItem) -> RequirementItem:
    db.flush()
    return item
