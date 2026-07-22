import logging
import re
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access.service import list_accessible_projects, require_project_capability
from app.audit.service import record_audit_event
from app.auth.schemas import CurrentUser
from app.models import Project, ProjectMember

from .repository import (
    create_project,
    count_project_members_by_role,
    delete_project,
    delete_project_for_org,
    get_active_user_for_org,
    get_project_member,
    get_project,
    get_project_for_org,
    list_project_members,
    list_projects,
    update_project_status,
    update_project_status_for_org,
)
from .schemas import (
    ProjectCreate,
    ProjectMemberCreate,
    ProjectMemberRead,
    ProjectMemberUpdate,
    ProjectRead,
)


logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:100] or "untitled"


def _unique_slug(db: Session, base_slug: str) -> str:
    slug = base_slug
    for _ in range(10):
        exists = db.scalar(select(Project.id).where(Project.slug == slug))
        if not exists:
            return slug
        slug = f"{base_slug[:90]}-{uuid.uuid4().hex[:6]}"
    return f"{base_slug[:80]}-{uuid.uuid4().hex[:12]}"


def create_project_command(
    db: Session,
    payload: ProjectCreate,
    org_id: str,
    actor_id: str,
) -> ProjectRead:
    project = _create_project_with_defaults(db, payload, org_id, actor_id)
    db.commit()
    db.refresh(project)
    return _project_to_read(project)


def _create_project_with_defaults(
    db: Session,
    payload: ProjectCreate,
    org_id: str,
    actor_id: str,
) -> Project:
    """Build a project and its standard sections without committing the unit of work."""

    sections: list[dict[str, str]] = []
    if payload.scenario_package:
        try:
            from app.scenarios.templates import get_sections_for_scenario

            sections = get_sections_for_scenario(payload.scenario_package)
        except ValueError as exc:
            # Existing callers may carry an older scenario key. Preserve the
            # project while making the missing template explicit in logs.
            logger.warning("Failed to resolve default sections: %s", exc)

    base_slug = _slugify(payload.name)
    slug = _unique_slug(db, base_slug)
    project = Project(
        name=payload.name,
        slug=slug,
        scenario_package=payload.scenario_package,
        org_id=org_id,
    )
    project = create_project(db, project)
    db.add(ProjectMember(project_id=project.id, user_id=actor_id, role="owner"))
    record_audit_event(
        db,
        project_id=project.id,
        event_type="project.created",
        actor_type="user",
        actor_id=actor_id,
    )

    if sections:
        from app.models import Deliverable, DeliverableSection

        deliverable = Deliverable(
            project_id=project.id,
            type=project.scenario_package,
            title=f"{payload.name} Deliverable",
        )
        db.add(deliverable)
        db.flush()

        for sec_def in sections:
            section = DeliverableSection(
                deliverable_id=deliverable.id,
                section_key=sec_def["section_key"],
                title=sec_def["title"],
            )
            db.add(section)

    return project


def _project_to_read(p: Project) -> ProjectRead:
    return ProjectRead(
        id=p.id, slug=p.slug, name=p.name,
        scenario_package=p.scenario_package, status=p.status,
        org_id=p.org_id, org_slug="",
    )


def get_project_query(db: Session, project_id: str) -> ProjectRead | None:
    project = get_project(db, project_id)
    if project is None:
        return None
    return _project_to_read(project)


def get_project_query_for_org(db: Session, project_id: str, org_id: str) -> ProjectRead | None:
    project = get_project_for_org(db, project_id, org_id)
    if project is None:
        return None
    return _project_to_read(project)


def list_projects_query(db: Session, org_id: str | None = None) -> list[ProjectRead]:
    projects = list_projects(db, org_id)
    return [_project_to_read(p) for p in projects]


def list_projects_query_for_user(db: Session, current_user: CurrentUser) -> list[ProjectRead]:
    return [_project_to_read(project) for project in list_accessible_projects(db, current_user=current_user)]


def get_project_query_for_user(
    db: Session,
    project_id: str,
    current_user: CurrentUser,
) -> ProjectRead:
    return _project_to_read(
        require_project_capability(
            db,
            current_user=current_user,
            project_id=project_id,
            capability="project.read",
        ).project
    )


def update_project_status_command(db: Session, project_id: str, status: str) -> ProjectRead | None:
    project = update_project_status(db, project_id, status)
    if project is None:
        return None
    return _project_to_read(project)


def update_project_status_command_for_org(db: Session, project_id: str, org_id: str, status: str) -> ProjectRead | None:
    project = update_project_status_for_org(db, project_id, org_id, status)
    if project is None:
        return None
    return _project_to_read(project)


def update_project_status_command_for_user(
    db: Session,
    project_id: str,
    status: str,
    current_user: CurrentUser,
) -> ProjectRead:
    access = require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.manage",
    )
    access.project.status = status
    record_audit_event(
        db,
        project_id=access.project.id,
        event_type="project.status_updated",
        actor_type="user",
        actor_id=current_user.id,
        payload={"status": status},
    )
    db.commit()
    db.refresh(access.project)
    return _project_to_read(access.project)


def delete_project_command(db: Session, project_id: str) -> bool:
    return delete_project(db, project_id)


def delete_project_command_for_org(db: Session, project_id: str, org_id: str) -> bool:
    return delete_project_for_org(db, project_id, org_id)


def delete_project_command_for_user(
    db: Session,
    project_id: str,
    current_user: CurrentUser,
) -> None:
    access = require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.delete",
    )
    record_audit_event(
        db,
        project_id=access.project.id,
        event_type="project.deleted",
        actor_type="user",
        actor_id=current_user.id,
    )
    access.project.status = "deleted"
    db.commit()


def list_project_members_query(
    db: Session,
    project_id: str,
    current_user: CurrentUser,
) -> list[ProjectMemberRead]:
    require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.read",
    )
    return [_project_member_to_read(member) for member in list_project_members(db, project_id)]


def add_project_member_command(
    db: Session,
    project_id: str,
    payload: ProjectMemberCreate,
    current_user: CurrentUser,
) -> ProjectMemberRead:
    access = require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.members.manage",
    )
    user = get_active_user_for_org(db, payload.user_id, access.project.org_id)
    if user is None:
        raise HTTPException(status_code=400, detail="User is not an active organization member")
    if get_project_member(db, access.project.id, user.id) is not None:
        raise HTTPException(status_code=409, detail="User is already a project member")
    member = ProjectMember(project_id=access.project.id, user_id=user.id, role=payload.role)
    db.add(member)
    record_audit_event(
        db,
        project_id=access.project.id,
        event_type="project.member_added",
        actor_type="user",
        actor_id=current_user.id,
        payload={"user_id": user.id, "role": payload.role},
    )
    db.commit()
    db.refresh(member)
    member.user = user
    return _project_member_to_read(member)


def update_project_member_command(
    db: Session,
    project_id: str,
    user_id: str,
    payload: ProjectMemberUpdate,
    current_user: CurrentUser,
) -> ProjectMemberRead:
    access = require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.members.manage",
    )
    member = get_project_member(db, access.project.id, user_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Project member not found")
    if (
        member.role == "owner"
        and payload.role != "owner"
        and count_project_members_by_role(db, access.project.id, "owner") <= 1
    ):
        raise HTTPException(status_code=409, detail="Project must retain an owner")
    member.role = payload.role
    record_audit_event(
        db,
        project_id=access.project.id,
        event_type="project.member_role_updated",
        actor_type="user",
        actor_id=current_user.id,
        payload={"user_id": member.user_id, "role": member.role},
    )
    db.commit()
    db.refresh(member)
    return _project_member_to_read(member)


def remove_project_member_command(
    db: Session,
    project_id: str,
    user_id: str,
    current_user: CurrentUser,
) -> None:
    access = require_project_capability(
        db,
        current_user=current_user,
        project_id=project_id,
        capability="project.members.manage",
    )
    member = get_project_member(db, access.project.id, user_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Project member not found")
    if member.role == "owner" and count_project_members_by_role(db, access.project.id, "owner") <= 1:
        raise HTTPException(status_code=409, detail="Project must retain an owner")
    db.delete(member)
    record_audit_event(
        db,
        project_id=access.project.id,
        event_type="project.member_removed",
        actor_type="user",
        actor_id=current_user.id,
        payload={"user_id": user_id},
    )
    db.commit()


def _project_member_to_read(member: ProjectMember) -> ProjectMemberRead:
    return ProjectMemberRead(
        user_id=member.user_id,
        display_name=member.user.display_name if member.user is not None else member.user_id,
        role=member.role,
    )
