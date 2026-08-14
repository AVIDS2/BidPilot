from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.access.service import require_deliverable_section_capability, require_project_capability
from app.audit.service import record_audit_event
from app.auth.schemas import CurrentUser
from app.models import (
    ContentLibraryEntry,
    ContentLibraryUsage,
    ContentLibraryVersion,
)
from app.organizations.service import MEMBERSHIP_MANAGERS, MEMBERSHIP_ROLES, require_organization_role

from .schemas import (
    ContentLibraryEntryCreate,
    ContentLibraryEntryRead,
    ContentLibraryPublish,
    ContentLibraryUsageCreate,
    ContentLibraryUsageRead,
    ContentLibraryVersionCreate,
    ContentLibraryVersionRead,
)


def _org_id(current_user: CurrentUser) -> str:
    return current_user.org_id or "default"


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _require_org_member(db: Session, current_user: CurrentUser) -> str:
    org_id = _org_id(current_user)
    require_organization_role(
        db,
        org_id=org_id,
        user_id=current_user.id,
        allowed_roles=MEMBERSHIP_ROLES,
    )
    return org_id


def _require_library_manager(db: Session, current_user: CurrentUser) -> str:
    org_id = _org_id(current_user)
    require_organization_role(
        db,
        org_id=org_id,
        user_id=current_user.id,
        allowed_roles=MEMBERSHIP_MANAGERS,
    )
    return org_id


def _version_read(item: ContentLibraryVersion) -> ContentLibraryVersionRead:
    return ContentLibraryVersionRead(
        id=item.id,
        entry_id=item.entry_id,
        version_number=item.version_number,
        content_markdown=item.content_markdown,
        content_hash=item.content_hash,
        source_json=item.source_json,
        created_by_user_id=item.created_by_user_id,
        created_at=item.created_at,
    )


def _usage_read(item: ContentLibraryUsage) -> ContentLibraryUsageRead:
    return ContentLibraryUsageRead(
        id=item.id,
        entry_id=item.entry_id,
        content_version_id=item.content_version_id,
        project_id=item.project_id,
        deliverable_section_id=item.deliverable_section_id,
        usage_purpose=item.usage_purpose,
        used_by_user_id=item.used_by_user_id,
        created_at=item.created_at,
    )


def _entry_read(item: ContentLibraryEntry, *, include_versions: bool = True) -> ContentLibraryEntryRead:
    versions = sorted(item.versions, key=lambda version: version.version_number, reverse=True)
    readable_versions = [_version_read(version) for version in versions]
    return ContentLibraryEntryRead(
        id=item.id,
        org_id=item.org_id,
        title=item.title,
        content_type=item.content_type,
        category=item.category,
        tags_json=item.tags_json or [],
        lifecycle_status=item.lifecycle_status,  # type: ignore[arg-type]
        review_status=item.review_status,  # type: ignore[arg-type]
        owner_user_id=item.owner_user_id,
        effective_from=item.effective_from,
        effective_until=item.effective_until,
        supersedes_entry_id=item.supersedes_entry_id,
        created_at=item.created_at,
        updated_at=item.updated_at,
        latest_version=readable_versions[0] if readable_versions else None,
        versions=readable_versions if include_versions else [],
    )


def _entry_query(db: Session, *, entry_id: str, org_id: str, for_update: bool = False) -> ContentLibraryEntry | None:
    statement = (
        select(ContentLibraryEntry)
        .options(selectinload(ContentLibraryEntry.versions))
        .where(ContentLibraryEntry.id == entry_id, ContentLibraryEntry.org_id == org_id)
        # Publish/version commands can run after a list or get query in the
        # same Session; always materialize the latest immutable version set.
        .execution_options(populate_existing=True)
    )
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def list_content_library_query(
    db: Session,
    *,
    current_user: CurrentUser,
    lifecycle_status: str | None = None,
    category: str | None = None,
) -> list[ContentLibraryEntryRead]:
    org_id = _require_org_member(db, current_user)
    statement = (
        select(ContentLibraryEntry)
        .options(selectinload(ContentLibraryEntry.versions))
        .where(ContentLibraryEntry.org_id == org_id)
        .order_by(ContentLibraryEntry.updated_at.desc(), ContentLibraryEntry.id.desc())
    )
    if lifecycle_status is not None:
        statement = statement.where(ContentLibraryEntry.lifecycle_status == lifecycle_status)
    if category is not None:
        statement = statement.where(ContentLibraryEntry.category == category)
    return [_entry_read(entry, include_versions=False) for entry in db.scalars(statement).all()]


def get_content_library_entry_query(
    db: Session,
    *,
    entry_id: str,
    current_user: CurrentUser,
) -> ContentLibraryEntryRead:
    org_id = _require_org_member(db, current_user)
    entry = _entry_query(db, entry_id=entry_id, org_id=org_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Content library entry not found")
    return _entry_read(entry)


def _content_hash(markdown: str) -> str:
    return hashlib.sha256(markdown.encode("utf-8")).hexdigest()


def create_content_library_entry_command(
    db: Session,
    *,
    payload: ContentLibraryEntryCreate,
    current_user: CurrentUser,
) -> ContentLibraryEntryRead:
    org_id = _require_library_manager(db, current_user)
    if payload.supersedes_entry_id:
        predecessor = _entry_query(db, entry_id=payload.supersedes_entry_id, org_id=org_id)
        if predecessor is None:
            raise HTTPException(status_code=422, detail="Superseded content entry must belong to this organization")
    entry = ContentLibraryEntry(
        org_id=org_id,
        title=payload.title.strip(),
        content_type=payload.content_type,
        category=payload.category,
        tags_json=payload.tags_json,
        owner_user_id=current_user.id,
        effective_from=payload.effective_from,
        effective_until=payload.effective_until,
        supersedes_entry_id=payload.supersedes_entry_id,
    )
    db.add(entry)
    db.flush()
    db.add(
        ContentLibraryVersion(
            entry_id=entry.id,
            version_number=1,
            content_markdown=payload.content_markdown,
            content_hash=_content_hash(payload.content_markdown),
            source_json=payload.source_json,
            created_by_user_id=current_user.id,
        )
    )
    db.commit()
    created = _entry_query(db, entry_id=entry.id, org_id=org_id)
    assert created is not None
    return _entry_read(created)


def create_content_library_version_command(
    db: Session,
    *,
    entry_id: str,
    payload: ContentLibraryVersionCreate,
    current_user: CurrentUser,
) -> ContentLibraryEntryRead:
    org_id = _require_library_manager(db, current_user)
    entry = _entry_query(db, entry_id=entry_id, org_id=org_id, for_update=True)
    if entry is None:
        raise HTTPException(status_code=404, detail="Content library entry not found")
    content_hash = _content_hash(payload.content_markdown)
    for version in entry.versions:
        if version.content_hash == content_hash:
            raise HTTPException(status_code=409, detail="This content version already exists")
    next_version = max((version.version_number for version in entry.versions), default=0) + 1
    db.add(
        ContentLibraryVersion(
            entry_id=entry.id,
            version_number=next_version,
            content_markdown=payload.content_markdown,
            content_hash=content_hash,
            source_json=payload.source_json,
            created_by_user_id=current_user.id,
        )
    )
    entry.lifecycle_status = "draft"
    entry.review_status = "draft"
    db.commit()
    refreshed = _entry_query(db, entry_id=entry.id, org_id=org_id)
    assert refreshed is not None
    return _entry_read(refreshed)


def publish_content_library_entry_command(
    db: Session,
    *,
    entry_id: str,
    payload: ContentLibraryPublish,
    current_user: CurrentUser,
) -> ContentLibraryEntryRead:
    org_id = _require_library_manager(db, current_user)
    entry = _entry_query(db, entry_id=entry_id, org_id=org_id, for_update=True)
    if entry is None:
        raise HTTPException(status_code=404, detail="Content library entry not found")
    if not entry.versions:
        raise HTTPException(status_code=409, detail="Content library entry requires an immutable version before publishing")
    if payload.effective_from and payload.effective_until and payload.effective_from >= payload.effective_until:
        raise HTTPException(status_code=422, detail="effective_until must be later than effective_from")
    entry.lifecycle_status = "published"
    entry.review_status = "approved"
    entry.effective_from = payload.effective_from or entry.effective_from
    entry.effective_until = payload.effective_until
    db.commit()
    refreshed = _entry_query(db, entry_id=entry.id, org_id=org_id)
    assert refreshed is not None
    return _entry_read(refreshed)


def archive_content_library_entry_command(
    db: Session,
    *,
    entry_id: str,
    current_user: CurrentUser,
) -> ContentLibraryEntryRead:
    org_id = _require_library_manager(db, current_user)
    entry = _entry_query(db, entry_id=entry_id, org_id=org_id, for_update=True)
    if entry is None:
        raise HTTPException(status_code=404, detail="Content library entry not found")
    entry.lifecycle_status = "archived"
    db.commit()
    refreshed = _entry_query(db, entry_id=entry.id, org_id=org_id)
    assert refreshed is not None
    return _entry_read(refreshed)


def apply_content_library_entry_command(
    db: Session,
    *,
    entry_id: str,
    payload: ContentLibraryUsageCreate,
    current_user: CurrentUser,
) -> ContentLibraryUsageRead:
    org_id = _require_org_member(db, current_user)
    entry = _entry_query(db, entry_id=entry_id, org_id=org_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Content library entry not found")
    if entry.lifecycle_status != "published" or entry.review_status != "approved":
        raise HTTPException(status_code=409, detail="Only approved published content can be reused")
    now = _now()
    if (entry.effective_from and entry.effective_from > now) or (
        entry.effective_until and entry.effective_until <= now
    ):
        raise HTTPException(status_code=409, detail="Content library entry is outside its effective period")
    access = require_project_capability(
        db,
        current_user=current_user,
        project_id=payload.project_id,
        capability="project.manage",
    )
    if access.project.org_id != org_id:
        raise HTTPException(status_code=404, detail="Project not found")
    if payload.deliverable_section_id:
        section = require_deliverable_section_capability(
            db,
            current_user=current_user,
            section_id=payload.deliverable_section_id,
            capability="project.manage",
        )
        if section.deliverable.project_id != payload.project_id:
            raise HTTPException(status_code=422, detail="Deliverable section must belong to the selected project")

    versions_by_id = {version.id: version for version in entry.versions}
    selected = versions_by_id.get(payload.content_version_id) if payload.content_version_id else None
    if payload.content_version_id and selected is None:
        raise HTTPException(status_code=422, detail="Content version does not belong to this entry")
    if selected is None:
        selected = max(entry.versions, key=lambda version: version.version_number, default=None)
    if selected is None:
        raise HTTPException(status_code=409, detail="Content library entry has no version")

    statement = select(ContentLibraryUsage).where(
        ContentLibraryUsage.content_version_id == selected.id,
        ContentLibraryUsage.project_id == payload.project_id,
        ContentLibraryUsage.usage_purpose == payload.usage_purpose,
    )
    statement = statement.where(
        ContentLibraryUsage.deliverable_section_id == payload.deliverable_section_id
        if payload.deliverable_section_id
        else ContentLibraryUsage.deliverable_section_id.is_(None)
    )
    usage = db.scalar(statement)
    if usage is None:
        usage = ContentLibraryUsage(
            entry_id=entry.id,
            content_version_id=selected.id,
            project_id=payload.project_id,
            deliverable_section_id=payload.deliverable_section_id,
            usage_purpose=payload.usage_purpose,
            used_by_user_id=current_user.id,
        )
        db.add(usage)
        db.flush()
        record_audit_event(
            db,
            project_id=payload.project_id,
            event_type="content_library.applied",
            actor_type="user",
            actor_id=current_user.id,
            payload={"entry_id": entry.id, "content_version_id": selected.id, "usage_id": usage.id},
        )
        db.commit()
    return _usage_read(usage)
