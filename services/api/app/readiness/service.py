from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.adapters.storage import download_bytes, upload_bytes
from app.audit.service import record_audit_event
from app.models import ReadinessPack, RequirementItem

from .exporters import render_readiness_docx, render_readiness_xlsx
from .repository import (
    get_pack_for_org,
    get_project_for_org,
    list_project_requirements,
    next_pack_version,
)
from .schemas import (
    BidReadinessSummary,
    ReadinessCounts,
    ReadinessPackRead,
    ReadinessRequirementRead,
    ReadinessScores,
    ReadinessWorkload,
)


FORMULA_VERSION = "1.0"


def get_readiness_summary_query(
    db: Session,
    project_id: str,
    *,
    org_id: str,
) -> BidReadinessSummary:
    project = get_project_for_org(db, project_id, org_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    requirements = list_project_requirements(db, project_id)
    return _build_summary(project.id, project.name, requirements)


def generate_readiness_pack_command(
    db: Session,
    project_id: str,
    *,
    org_id: str,
    actor_id: str,
) -> ReadinessPackRead:
    project = get_project_for_org(db, project_id, org_id, for_update=True)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    requirements = list_project_requirements(db, project_id)
    summary = _build_summary(project.id, project.name, requirements)
    version_number = next_pack_version(db, project_id)
    pack = ReadinessPack(
        id=str(uuid.uuid4()),
        project_id=project_id,
        version_number=version_number,
        formula_version=summary.formula_version,
        source_fingerprint=summary.source_fingerprint,
        status="generating",
        summary_json=summary.model_dump(mode="json"),
        generated_by_user_id=actor_id,
    )
    db.add(pack)
    db.flush()

    xlsx_bytes = render_readiness_xlsx(summary)
    docx_bytes = render_readiness_docx(summary)
    base_name = f"readiness/{pack.id}/v{version_number}"
    xlsx_object = f"{base_name}/bid-readiness.xlsx"
    docx_object = f"{base_name}/bid-readiness.docx"
    try:
        pack.xlsx_storage_key = upload_bytes(
            project_id,
            xlsx_object,
            xlsx_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        pack.docx_storage_key = upload_bytes(
            project_id,
            docx_object,
            docx_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Readiness artifact storage unavailable") from exc

    pack.status = "generated"
    record_audit_event(
        db,
        project_id=project_id,
        event_type="readiness_pack.generated",
        actor_type="user",
        actor_id=actor_id,
        payload={
            "pack_id": pack.id,
            "version_number": version_number,
            "source_fingerprint": pack.source_fingerprint,
        },
    )
    db.commit()
    db.refresh(pack)
    return ReadinessPackRead.model_validate(pack)


def download_readiness_pack_query(
    db: Session,
    pack_id: str,
    artifact_format: str,
    *,
    org_id: str,
) -> tuple[bytes, str, str]:
    pack = get_pack_for_org(db, pack_id, org_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="Readiness pack not found")
    if artifact_format == "xlsx":
        storage_key = pack.xlsx_storage_key
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif artifact_format == "docx":
        storage_key = pack.docx_storage_key
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        raise HTTPException(status_code=400, detail="Unsupported readiness artifact format")
    if not storage_key or "/" not in storage_key:
        raise HTTPException(status_code=404, detail="Readiness artifact is unavailable")
    object_name = storage_key.split("/", 1)[1]
    try:
        data = download_bytes(pack.project_id, object_name)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Readiness artifact storage unavailable") from exc
    filename = f"bid-readiness-v{pack.version_number}.{artifact_format}"
    return data, media_type, filename


def _build_summary(
    project_id: str,
    project_name: str,
    requirements: list[RequirementItem],
) -> BidReadinessSummary:
    rows = [_requirement_to_read(requirement) for requirement in requirements]
    mandatory = [row for row in rows if row.is_mandatory]
    scored = [row for row in rows if (row.score_weight or 0) > 0]
    now = datetime.now(UTC).replace(tzinfo=None)

    coverage_counts = Counter(row.coverage_status for row in rows)
    mandatory_closure = _average([_coverage_factor(row.coverage_status) for row in mandatory])
    total_score_weight = sum(row.score_weight or 0 for row in scored)
    scored_coverage = (
        sum((row.score_weight or 0) * _coverage_factor(row.coverage_status) for row in scored)
        / total_score_weight
        if total_score_weight
        else _average([_coverage_factor(row.coverage_status) for row in rows])
    )
    verification = _ratio(
        sum(row.verification_status == "verified" for row in rows),
        len(rows),
    )
    assignment = _ratio(sum(row.owner_user_id is not None for row in rows), len(rows))
    readiness_score = round(
        100
        * (
            0.4 * mandatory_closure
            + 0.3 * scored_coverage
            + 0.2 * verification
            + 0.1 * assignment
        ),
        1,
    )

    fingerprint_payload = [
        {
            "id": requirement.id,
            "lock_version": requirement.lock_version,
            "verification_status": requirement.verification_status,
            "owner_user_id": requirement.owner_user_id,
            "profile": {
                "coverage_status": requirement.bid_profile.coverage_status
                if requirement.bid_profile
                else "uncovered",
                "evidence_status": requirement.bid_profile.evidence_status
                if requirement.bid_profile
                else "missing",
                "risk_level": requirement.bid_profile.risk_level
                if requirement.bid_profile
                else "normal",
                "score_weight": requirement.bid_profile.score_weight
                if requirement.bid_profile
                else None,
            },
        }
        for requirement in requirements
    ]
    source_fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    by_owner = Counter(row.owner_user_id for row in rows if row.owner_user_id)
    return BidReadinessSummary(
        formula_version=FORMULA_VERSION,
        project_id=project_id,
        project_name=project_name,
        generated_at=datetime.now(UTC),
        source_fingerprint=source_fingerprint,
        readiness_score=readiness_score,
        counts=ReadinessCounts(
            total=len(rows),
            mandatory=len(mandatory),
            scored=len(scored),
            covered=coverage_counts["covered"],
            partial=coverage_counts["partial"],
            uncovered=coverage_counts["uncovered"],
            disputed=coverage_counts["disputed"],
            not_applicable=coverage_counts["not_applicable"],
            accepted_risk=coverage_counts["accepted_risk"],
            verified=sum(row.verification_status == "verified" for row in rows),
            assigned=sum(row.owner_user_id is not None for row in rows),
        ),
        scores=ReadinessScores(
            mandatory_closure=mandatory_closure,
            scored_coverage=scored_coverage,
            verification=verification,
            assignment=assignment,
        ),
        requirements=rows,
        mandatory_gaps=[row for row in mandatory if _coverage_factor(row.coverage_status) < 1],
        evidence_gaps=[
            row
            for row in rows
            if row.evidence_status in {"missing", "weak", "conflicting"}
            and row.coverage_status != "not_applicable"
        ],
        contradictions=[
            row
            for row in rows
            if row.coverage_status == "disputed" or row.evidence_status == "conflicting"
        ],
        overdue=[
            row
            for row in rows
            if row.due_at is not None
            and row.due_at < now
            and row.coverage_status not in {"covered", "not_applicable"}
        ],
        qualifications=[row for row in rows if row.bid_category == "qualification"],
        workload=ReadinessWorkload(
            unassigned=sum(row.owner_user_id is None for row in rows),
            by_owner=dict(by_owner),
        ),
    )


def _requirement_to_read(requirement: RequirementItem) -> ReadinessRequirementRead:
    profile = requirement.bid_profile
    return ReadinessRequirementRead(
        id=requirement.id,
        section_key=requirement.section_key,
        requirement_text=requirement.requirement_text,
        bid_category=profile.bid_category if profile else "unclassified",
        is_mandatory=profile.is_mandatory if profile else False,
        score_weight=profile.score_weight if profile else None,
        risk_level=profile.risk_level if profile else "normal",
        coverage_status=profile.coverage_status if profile else "uncovered",
        evidence_status=profile.evidence_status if profile else "missing",
        verification_status=requirement.verification_status,
        owner_user_id=requirement.owner_user_id,
        reviewer_user_id=requirement.reviewer_user_id,
        due_at=requirement.due_at,
        source_locator_json=requirement.source_locator_json,
    )


def _coverage_factor(status: str) -> float:
    return {
        "covered": 1.0,
        "not_applicable": 1.0,
        "partial": 0.5,
        "accepted_risk": 0.25,
        "uncovered": 0.0,
        "disputed": 0.0,
    }.get(status, 0.0)


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


__all__ = [
    "download_readiness_pack_query",
    "generate_readiness_pack_command",
    "get_readiness_summary_query",
]

