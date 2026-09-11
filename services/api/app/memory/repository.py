from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session

from app.access.service import ROLE_CAPABILITIES, list_accessible_projects
from app.auth.schemas import CurrentUser
from app.models import MemoryCompilationRun, MemoryEvidenceLink, MemoryRecord, ProjectMember


@dataclass(frozen=True)
class MemoryPortfolioRow:
    """Safe, aggregate-only project knowledge metadata for the portfolio."""

    project_id: str
    project_name: str
    active_shared_count: int
    proposed_shared_count: int | None
    latest_shared_memory_at: datetime | None
    latest_compilation_status: str | None
    latest_compilation_at: datetime | None


@dataclass(frozen=True)
class MemoryEvidenceMapRecordRow:
    id: str
    title: str
    kind: str


@dataclass(frozen=True)
class MemoryEvidenceMapCitationRow:
    memory_record_id: str
    source_type: str
    source_id: str
    label: str


@dataclass(frozen=True)
class MemoryEvidenceMapRows:
    records: tuple[MemoryEvidenceMapRecordRow, ...]
    citations: tuple[MemoryEvidenceMapCitationRow, ...]
    truncated: bool


def get_memory_record(db: Session, memory_id: str) -> MemoryRecord | None:
    return db.get(MemoryRecord, memory_id)


def list_memory_records(
    db: Session,
    *,
    org_id: str,
    project_id: str | None,
    owner_user_id: str | None,
    include_proposed: bool,
    include_history: bool = False,
    scope: str | None = None,
) -> list[MemoryRecord]:
    stmt: Select[tuple[MemoryRecord]] = select(MemoryRecord).where(
        MemoryRecord.org_id == org_id,
        MemoryRecord.deleted_at.is_(None),
    )
    if project_id is not None:
        stmt = stmt.where(MemoryRecord.project_id == project_id)
    if owner_user_id is not None:
        stmt = stmt.where(MemoryRecord.owner_user_id == owner_user_id)
    if scope is not None:
        stmt = stmt.where(MemoryRecord.scope == scope)
    if include_history:
        stmt = stmt.where(MemoryRecord.status.in_(("active", "proposed", "superseded", "rejected")))
    elif include_proposed:
        stmt = stmt.where(MemoryRecord.status.in_(("active", "proposed")))
    else:
        stmt = stmt.where(MemoryRecord.status == "active")
    return list(db.scalars(stmt.order_by(MemoryRecord.updated_at.desc(), MemoryRecord.id.asc())).all())


def list_memory_portfolio_rows(
    db: Session,
    *,
    current_user: CurrentUser,
    limit: int,
) -> list[MemoryPortfolioRow]:
    """Return only project-shared knowledge health for already-visible projects.

    The portfolio is a discovery index, not a cross-project memory query. It
    intentionally obtains project visibility from the access service before
    aggregating any memory data, and it never reads user-private records.
    """

    projects = list_accessible_projects(db, current_user=current_user)
    project_ids = [project.id for project in projects]
    if not project_ids:
        return []

    org_id = current_user.org_id or "default"
    active_count = func.coalesce(
        func.sum(case((MemoryRecord.status == "active", 1), else_=0)),
        0,
    ).label("active_shared_count")
    proposed_count = func.coalesce(
        func.sum(case((MemoryRecord.status == "proposed", 1), else_=0)),
        0,
    ).label("proposed_shared_count")
    memory_rows = db.execute(
        select(
            MemoryRecord.project_id,
            active_count,
            proposed_count,
            func.max(MemoryRecord.updated_at).label("latest_shared_memory_at"),
        )
        .where(
            MemoryRecord.org_id == org_id,
            MemoryRecord.project_id.in_(project_ids),
            MemoryRecord.scope == "project_shared",
            MemoryRecord.status.in_(("active", "proposed")),
            MemoryRecord.deleted_at.is_(None),
            or_(MemoryRecord.expires_at.is_(None), MemoryRecord.expires_at > func.now()),
        )
        .group_by(MemoryRecord.project_id)
    ).all()
    memory_by_project = {
        project_id: (int(active or 0), int(proposed or 0), latest)
        for project_id, active, proposed, latest in memory_rows
    }

    compilation_rows = db.execute(
        select(
            MemoryCompilationRun.project_id,
            MemoryCompilationRun.status,
            MemoryCompilationRun.created_at,
        )
        .where(
            MemoryCompilationRun.org_id == org_id,
            MemoryCompilationRun.project_id.in_(project_ids),
        )
        .order_by(
            MemoryCompilationRun.project_id.asc(),
            MemoryCompilationRun.created_at.desc(),
            MemoryCompilationRun.id.desc(),
        )
    ).all()
    latest_compilation_by_project: dict[str, tuple[str, datetime]] = {}
    for project_id, status, created_at in compilation_rows:
        latest_compilation_by_project.setdefault(project_id, (status, created_at))

    if current_user.role == "admin":
        approver_project_ids = set(project_ids)
    else:
        approver_roles = {
            role
            for role, capabilities in ROLE_CAPABILITIES.items()
            if "memory.approve" in capabilities
        }
        approver_project_ids = set(
            db.scalars(
                select(ProjectMember.project_id).where(
                    ProjectMember.user_id == current_user.id,
                    ProjectMember.project_id.in_(project_ids),
                    ProjectMember.role.in_(approver_roles),
                )
            ).all()
        )

    rows = []
    for project in projects:
        active, proposed, latest_memory = memory_by_project.get(project.id, (0, 0, None))
        latest_compilation = latest_compilation_by_project.get(project.id)
        rows.append(
            MemoryPortfolioRow(
                project_id=project.id,
                project_name=project.name,
                active_shared_count=active,
                proposed_shared_count=proposed if project.id in approver_project_ids else None,
                latest_shared_memory_at=latest_memory,
                latest_compilation_status=latest_compilation[0] if latest_compilation else None,
                latest_compilation_at=latest_compilation[1] if latest_compilation else None,
            )
        )

    rows.sort(
        key=lambda row: (
            row.latest_shared_memory_at or datetime.min,
            row.latest_compilation_at or datetime.min,
            row.project_id,
        ),
        reverse=True,
    )
    return rows[:limit]


def list_project_evidence_map_rows(
    db: Session,
    *,
    org_id: str,
    project_id: str,
    max_records: int,
) -> MemoryEvidenceMapRows:
    """Load a bounded, active shared-memory provenance projection.

    The caller has already passed project capability checks. This repository
    intentionally leaves source identifiers internal so the service can issue
    opaque graph node ids instead of turning the map into a source API.
    """
    record_rows = db.execute(
        select(MemoryRecord.id, MemoryRecord.title, MemoryRecord.kind)
        .where(
            MemoryRecord.org_id == org_id,
            MemoryRecord.project_id == project_id,
            MemoryRecord.scope == "project_shared",
            MemoryRecord.status == "active",
            MemoryRecord.deleted_at.is_(None),
            or_(MemoryRecord.expires_at.is_(None), MemoryRecord.expires_at > func.now()),
        )
        .order_by(MemoryRecord.updated_at.desc(), MemoryRecord.id.asc())
        .limit(max_records + 1)
    ).all()
    truncated = len(record_rows) > max_records
    visible_records = tuple(
        MemoryEvidenceMapRecordRow(id=record_id, title=title, kind=kind)
        for record_id, title, kind in record_rows[:max_records]
    )
    if not visible_records:
        return MemoryEvidenceMapRows(records=(), citations=(), truncated=truncated)

    # MemoryCreate caps citations at 32. A single bounded query keeps the map
    # deterministic while avoiding a record-by-record lookup.
    max_links = max_records * 32 + 1
    citation_rows = db.execute(
        select(
            MemoryEvidenceLink.memory_record_id,
            MemoryEvidenceLink.source_type,
            MemoryEvidenceLink.source_id,
            MemoryEvidenceLink.label,
        )
        .where(MemoryEvidenceLink.memory_record_id.in_([record.id for record in visible_records]))
        .order_by(MemoryEvidenceLink.memory_record_id.asc(), MemoryEvidenceLink.id.asc())
        .limit(max_links)
    ).all()
    if len(citation_rows) > max_records * 32:
        truncated = True
    return MemoryEvidenceMapRows(
        records=visible_records,
        citations=tuple(
            MemoryEvidenceMapCitationRow(
                memory_record_id=memory_record_id,
                source_type=source_type,
                source_id=source_id,
                label=label,
            )
            for memory_record_id, source_type, source_id, label in citation_rows[: max_records * 32]
        ),
        truncated=truncated,
    )
