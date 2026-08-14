from __future__ import annotations

import difflib
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.access.service import require_project_capability
from app.audit.service import record_audit_event
from app.auth.schemas import CurrentUser
from app.models import (
    Bundle,
    DocumentChangeImpact,
    DocumentChangeSet,
    Notification,
    ParsedAsset,
    RequirementItem,
    SourceDocument,
)

from .schemas import (
    DocumentChangeImpactRead,
    DocumentChangeImpactUpdate,
    DocumentChangeSetCreate,
    DocumentChangeSetDecision,
    DocumentChangeSetRead,
)


MAX_DIFF_CHARACTERS = 250_000
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _impact_read(item: DocumentChangeImpact) -> DocumentChangeImpactRead:
    return DocumentChangeImpactRead(
        id=item.id,
        impact_key=item.impact_key,
        requirement_id=item.requirement_id,
        deliverable_section_id=item.deliverable_section_id,
        impact_type=item.impact_type,
        severity=item.severity,  # type: ignore[arg-type]
        status=item.status,  # type: ignore[arg-type]
        summary=item.summary,
        locator_json=item.locator_json,
        acknowledged_by_user_id=item.acknowledged_by_user_id,
        acknowledged_at=item.acknowledged_at,
        resolved_by_user_id=item.resolved_by_user_id,
        resolved_at=item.resolved_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _change_set_read(item: DocumentChangeSet) -> DocumentChangeSetRead:
    impacts = sorted(
        item.impacts,
        key=lambda impact: (
            _SEVERITY_ORDER.get(impact.severity, len(_SEVERITY_ORDER)),
            impact.created_at or _now(),
            impact.id,
        ),
    )
    return DocumentChangeSetRead(
        id=item.id,
        project_id=item.project_id,
        previous_document_id=item.previous_document_id,
        replacement_document_id=item.replacement_document_id,
        status=item.status,  # type: ignore[arg-type]
        summary_json=item.summary_json or {},
        created_by_user_id=item.created_by_user_id,
        reviewed_by_user_id=item.reviewed_by_user_id,
        reviewed_at=item.reviewed_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
        impacts=[_impact_read(impact) for impact in impacts],
    )


def _load_change_set(
    db: Session,
    *,
    change_set_id: str,
    project_id: str | None = None,
    for_update: bool = False,
) -> DocumentChangeSet | None:
    statement = (
        select(DocumentChangeSet)
        .options(selectinload(DocumentChangeSet.impacts))
        .where(DocumentChangeSet.id == change_set_id)
        # Command handlers may create impacts after the relationship was first
        # loaded.  The returned read model must reflect the just-committed
        # project truth, not the Session's previous empty collection.
        .execution_options(populate_existing=True)
    )
    if project_id is not None:
        statement = statement.where(DocumentChangeSet.project_id == project_id)
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def _require_project_manager(db: Session, current_user: CurrentUser, project_id: str) -> None:
    require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.manage",
    )


def _parsed_text(db: Session, document_id: str) -> str | None:
    asset = db.scalar(
        select(ParsedAsset)
        .where(ParsedAsset.source_document_id == document_id)
        .order_by(ParsedAsset.created_at.desc(), ParsedAsset.id.desc())
        .limit(1)
    )
    if asset is None:
        return None
    content = asset.content_json
    if isinstance(content, dict):
        text = content.get("normalized_text") or content.get("text")
        return text if isinstance(text, str) and text.strip() else None
    if isinstance(content, str) and content.strip():
        return content
    return None


def _severity_for_requirement(requirement: RequirementItem) -> str:
    profile = requirement.bid_profile
    if profile is not None and profile.is_mandatory:
        return "critical"
    if profile is not None and profile.risk_level in {"high", "critical"}:
        return "high"
    return "medium"


def _diff_summary(previous_text: str, replacement_text: str) -> dict:
    truncated = len(previous_text) > MAX_DIFF_CHARACTERS or len(replacement_text) > MAX_DIFF_CHARACTERS
    previous = previous_text[:MAX_DIFF_CHARACTERS]
    replacement = replacement_text[:MAX_DIFF_CHARACTERS]
    before_lines = previous.splitlines()
    after_lines = replacement.splitlines()
    matcher = difflib.SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    changed_blocks: list[dict[str, int | str]] = []
    changed_before = 0
    changed_after = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        changed_before += i2 - i1
        changed_after += j2 - j1
        if len(changed_blocks) < 20:
            changed_blocks.append(
                {
                    "operation": tag,
                    "previous_start_line": i1 + 1,
                    "previous_end_line": i2,
                    "replacement_start_line": j1 + 1,
                    "replacement_end_line": j2,
                }
            )
    return {
        "analysis_status": "complete",
        "previous_line_count": len(before_lines),
        "replacement_line_count": len(after_lines),
        "changed_previous_lines": changed_before,
        "changed_replacement_lines": changed_after,
        "similarity_ratio": round(matcher.ratio(), 4),
        "comparison_truncated": truncated,
        "changed_blocks": changed_blocks,
    }


def _create_change_notifications(
    db: Session,
    *,
    requirements: list[RequirementItem],
    project_id: str,
    change_set_id: str,
) -> None:
    recipient_ids = {
        user_id
        for requirement in requirements
        for user_id in (requirement.owner_user_id, requirement.reviewer_user_id)
        if user_id
    }
    for user_id in recipient_ids:
        db.add(
            Notification(
                user_id=user_id,
                type="document_change",
                title="Source document changed",
                body="A requirement you own or review may be affected by a replacement document.",
                link=f"/projects/{project_id}/changes/{change_set_id}",
            )
        )


def create_document_change_set_command(
    db: Session,
    *,
    project_id: str,
    payload: DocumentChangeSetCreate,
    current_user: CurrentUser,
) -> DocumentChangeSetRead:
    _require_project_manager(db, current_user, project_id)
    replacement = db.scalar(
        select(SourceDocument).where(SourceDocument.id == payload.replacement_document_id).with_for_update()
    )
    if replacement is None or replacement.supersedes_document_id is None:
        raise HTTPException(status_code=422, detail="A replacement source document is required")
    bundle = db.get(Bundle, replacement.bundle_id)
    previous = db.get(SourceDocument, replacement.supersedes_document_id)
    if bundle is None or bundle.project_id != project_id or previous is None or previous.bundle_id != bundle.id:
        raise HTTPException(status_code=422, detail="Document replacement must remain within the selected project bundle")

    existing = db.scalar(
        select(DocumentChangeSet)
        .options(selectinload(DocumentChangeSet.impacts))
        .where(DocumentChangeSet.replacement_document_id == replacement.id)
    )
    if existing is not None:
        return _change_set_read(existing)

    change_set = DocumentChangeSet(
        project_id=project_id,
        previous_document_id=previous.id,
        replacement_document_id=replacement.id,
        status="pending_parse",
        summary_json={"analysis_status": "waiting_for_parse"},
        created_by_user_id=current_user.id,
    )
    db.add(change_set)
    db.flush()
    record_audit_event(
        db,
        project_id=project_id,
        event_type="document_change.created",
        actor_type="user",
        actor_id=current_user.id,
        payload={
            "change_set_id": change_set.id,
            "previous_document_id": previous.id,
            "replacement_document_id": replacement.id,
        },
    )
    db.commit()
    created = _load_change_set(db, change_set_id=change_set.id, project_id=project_id)
    assert created is not None
    return _change_set_read(created)


def analyze_document_change_set_command(
    db: Session,
    *,
    change_set_id: str,
    current_user: CurrentUser,
) -> DocumentChangeSetRead:
    initial = _load_change_set(db, change_set_id=change_set_id)
    if initial is None:
        raise HTTPException(status_code=404, detail="Document change set not found")
    _require_project_manager(db, current_user, initial.project_id)
    change_set = _load_change_set(
        db,
        change_set_id=change_set_id,
        project_id=initial.project_id,
        for_update=True,
    )
    assert change_set is not None
    if change_set.status in {"analyzed", "accepted", "dismissed"}:
        return _change_set_read(change_set)

    previous_text = _parsed_text(db, change_set.previous_document_id)
    replacement_text = _parsed_text(db, change_set.replacement_document_id)
    if not previous_text or not replacement_text:
        waiting = []
        if not previous_text:
            waiting.append(change_set.previous_document_id)
        if not replacement_text:
            waiting.append(change_set.replacement_document_id)
        change_set.status = "pending_parse"
        change_set.summary_json = {
            "analysis_status": "waiting_for_parse",
            "waiting_for_document_ids": waiting,
        }
        db.commit()
        refreshed = _load_change_set(db, change_set_id=change_set.id, project_id=change_set.project_id)
        assert refreshed is not None
        return _change_set_read(refreshed)

    summary = _diff_summary(previous_text, replacement_text)
    requirements = list(
        db.scalars(
            select(RequirementItem)
            .options(selectinload(RequirementItem.bid_profile))
            .where(
                RequirementItem.project_id == change_set.project_id,
                RequirementItem.source_document_id == change_set.previous_document_id,
            )
            .order_by(RequirementItem.id)
        ).all()
    )
    db.add(
        DocumentChangeImpact(
            change_set_id=change_set.id,
            impact_key="source-version",
            impact_type="source_document_replaced",
            severity="medium",
            summary="The replacement source document differs from the prior immutable version.",
            locator_json={"document_id": change_set.replacement_document_id},
        )
    )
    for requirement in requirements:
        db.add(
            DocumentChangeImpact(
                change_set_id=change_set.id,
                impact_key=f"requirement:{requirement.id}",
                requirement_id=requirement.id,
                impact_type="requirement_source_replaced",
                severity=_severity_for_requirement(requirement),
                summary="The source document version for this requirement was replaced; review coverage and evidence.",
                locator_json=requirement.source_locator_json,
            )
        )
    change_set.summary_json = {**summary, "impacted_requirement_count": len(requirements)}
    change_set.status = "analyzed"
    _create_change_notifications(
        db,
        requirements=requirements,
        project_id=change_set.project_id,
        change_set_id=change_set.id,
    )
    record_audit_event(
        db,
        project_id=change_set.project_id,
        event_type="document_change.analyzed",
        actor_type="user",
        actor_id=current_user.id,
        payload={"change_set_id": change_set.id, "impacted_requirement_count": len(requirements)},
    )
    db.commit()
    refreshed = _load_change_set(db, change_set_id=change_set.id, project_id=change_set.project_id)
    assert refreshed is not None
    return _change_set_read(refreshed)


def list_document_change_sets_query(
    db: Session,
    *,
    project_id: str,
    current_user: CurrentUser,
) -> list[DocumentChangeSetRead]:
    require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.read",
    )
    statement = (
        select(DocumentChangeSet)
        .options(selectinload(DocumentChangeSet.impacts))
        .where(DocumentChangeSet.project_id == project_id)
        .order_by(DocumentChangeSet.created_at.desc(), DocumentChangeSet.id.desc())
    )
    return [_change_set_read(change_set) for change_set in db.scalars(statement).all()]


def decide_document_change_set_command(
    db: Session,
    *,
    change_set_id: str,
    payload: DocumentChangeSetDecision,
    current_user: CurrentUser,
) -> DocumentChangeSetRead:
    initial = _load_change_set(db, change_set_id=change_set_id)
    if initial is None:
        raise HTTPException(status_code=404, detail="Document change set not found")
    _require_project_manager(db, current_user, initial.project_id)
    change_set = _load_change_set(
        db,
        change_set_id=change_set_id,
        project_id=initial.project_id,
        for_update=True,
    )
    assert change_set is not None
    if change_set.status == "pending_parse":
        raise HTTPException(status_code=409, detail="Analyze document change before accepting or dismissing it")
    change_set.status = payload.status
    change_set.reviewed_by_user_id = current_user.id
    change_set.reviewed_at = _now()
    record_audit_event(
        db,
        project_id=change_set.project_id,
        event_type=f"document_change.{payload.status}",
        actor_type="user",
        actor_id=current_user.id,
        payload={"change_set_id": change_set.id},
    )
    db.commit()
    refreshed = _load_change_set(db, change_set_id=change_set.id, project_id=change_set.project_id)
    assert refreshed is not None
    return _change_set_read(refreshed)


def update_document_change_impact_command(
    db: Session,
    *,
    change_set_id: str,
    impact_id: str,
    payload: DocumentChangeImpactUpdate,
    current_user: CurrentUser,
) -> DocumentChangeImpactRead:
    change_set = _load_change_set(db, change_set_id=change_set_id)
    if change_set is None:
        raise HTTPException(status_code=404, detail="Document change set not found")
    _require_project_manager(db, current_user, change_set.project_id)
    impact = db.scalar(
        select(DocumentChangeImpact)
        .where(DocumentChangeImpact.id == impact_id, DocumentChangeImpact.change_set_id == change_set.id)
        .with_for_update()
    )
    if impact is None:
        raise HTTPException(status_code=404, detail="Document change impact not found")
    impact.status = payload.status
    if payload.status == "acknowledged":
        impact.acknowledged_by_user_id = current_user.id
        impact.acknowledged_at = _now()
    if payload.status == "resolved":
        impact.resolved_by_user_id = current_user.id
        impact.resolved_at = _now()
    record_audit_event(
        db,
        project_id=change_set.project_id,
        event_type="document_change.impact_updated",
        actor_type="user",
        actor_id=current_user.id,
        payload={
            "change_set_id": change_set.id,
            "impact_id": impact.id,
            "impact_key": impact.impact_key,
            "status": impact.status,
        },
    )
    db.commit()
    return _impact_read(impact)
