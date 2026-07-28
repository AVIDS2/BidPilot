from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from contracts.access import (
    PROJECT_CAPABILITIES,
    ROLE_CAPABILITIES as ROLE_CAPABILITIES,
    project_role_has_capability,
)
from app.models import (
    Bundle,
    Deliverable,
    DeliverableSection,
    ExecutionRun,
    ParsedAsset,
    Project,
    ProjectMember,
    ReviewThread,
    SourceDocument,
)

from .schemas import ProjectAccess


def resolve_project_access(
    db: Session,
    *,
    current_user: CurrentUser,
    project_id: str,
) -> ProjectAccess | None:
    project = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.org_id == (current_user.org_id or "default"),
            Project.status != "deleted",
        )
    )
    if project is None:
        return None

    if current_user.role == "admin":
        return ProjectAccess(
            project=project,
            effective_role="admin",
            membership=None,
            used_admin_bypass=True,
        )

    membership = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == current_user.id,
        )
    )
    if membership is None:
        return None
    return ProjectAccess(
        project=project,
        effective_role=membership.role,
        membership=membership,
        used_admin_bypass=False,
    )


def list_accessible_projects(db: Session, *, current_user: CurrentUser) -> list[Project]:
    stmt = select(Project).where(
        Project.org_id == (current_user.org_id or "default"),
        Project.status != "deleted",
    )
    if current_user.role != "admin":
        stmt = stmt.join(ProjectMember).where(ProjectMember.user_id == current_user.id)
    stmt = stmt.order_by(Project.created_at.desc())
    return list(db.scalars(stmt).all())


def require_project_capability(
    db: Session,
    *,
    current_user: CurrentUser,
    project_id: str,
    capability: str,
) -> ProjectAccess:
    if capability not in PROJECT_CAPABILITIES:
        raise ValueError(f"Unknown project capability: {capability}")

    access = resolve_project_access(
        db,
        current_user=current_user,
        project_id=project_id,
    )
    if access is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if access.used_admin_bypass:
        return access
    if not project_role_has_capability(access.effective_role, capability):
        raise HTTPException(status_code=403, detail="Project capability required")
    return access


def require_bundle_capability(
    db: Session,
    *,
    current_user: CurrentUser,
    bundle_id: str,
    capability: str,
) -> Bundle:
    bundle = db.get(Bundle, bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Bundle not found")
    require_project_capability(
        db,
        current_user=current_user,
        project_id=bundle.project_id,
        capability=capability,
    )
    return bundle


def require_execution_run_capability(
    db: Session,
    *,
    current_user: CurrentUser,
    run_id: str,
    capability: str,
) -> ExecutionRun:
    run = db.get(ExecutionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Execution run not found")
    require_project_capability(
        db,
        current_user=current_user,
        project_id=run.project_id,
        capability=capability,
    )
    return run


def require_deliverable_capability(
    db: Session,
    *,
    current_user: CurrentUser,
    deliverable_id: str,
    capability: str,
) -> Deliverable:
    deliverable = db.get(Deliverable, deliverable_id)
    if deliverable is None:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    require_project_capability(
        db,
        current_user=current_user,
        project_id=deliverable.project_id,
        capability=capability,
    )
    return deliverable


def require_deliverable_section_capability(
    db: Session,
    *,
    current_user: CurrentUser,
    section_id: str,
    capability: str,
) -> DeliverableSection:
    section = db.get(DeliverableSection, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Deliverable section not found")
    deliverable = db.get(Deliverable, section.deliverable_id)
    if deliverable is None:
        raise HTTPException(status_code=404, detail="Deliverable section not found")
    require_project_capability(
        db,
        current_user=current_user,
        project_id=deliverable.project_id,
        capability=capability,
    )
    return section


def require_review_thread_capability(
    db: Session,
    *,
    current_user: CurrentUser,
    thread_id: str,
    capability: str,
) -> ReviewThread:
    thread = db.get(ReviewThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Review thread not found")
    require_deliverable_section_capability(
        db,
        current_user=current_user,
        section_id=thread.deliverable_section_id,
        capability=capability,
    )
    return thread


def require_source_document_capability(
    db: Session,
    *,
    current_user: CurrentUser,
    document_id: str,
    capability: str,
) -> SourceDocument:
    document = db.get(SourceDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    bundle = db.get(Bundle, document.bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Document not found")
    require_project_capability(
        db,
        current_user=current_user,
        project_id=bundle.project_id,
        capability=capability,
    )
    return document


def require_parsed_asset_capability(
    db: Session,
    *,
    current_user: CurrentUser,
    asset_id: str,
    capability: str,
) -> ParsedAsset:
    asset = db.get(ParsedAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Parsed asset not found")
    require_source_document_capability(
        db,
        current_user=current_user,
        document_id=asset.source_document_id,
        capability=capability,
    )
    return asset
