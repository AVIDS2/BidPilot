from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import OrganizationMembership, Project, ProjectMember, User


def create_project(db: Session, project: Project) -> Project:
    db.add(project)
    db.flush()
    return project


def get_project(db: Session, project_id: str) -> Project | None:
    return db.scalar(
        select(Project).where(Project.id == project_id, Project.status != "deleted")
    )


def get_project_for_org(db: Session, project_id: str, org_id: str) -> Project | None:
    stmt = select(Project).where(
        Project.id == project_id,
        Project.org_id == org_id,
        Project.status != "deleted",
    )
    return db.scalar(stmt)


def list_projects(db: Session, org_id: str | None = None) -> list[Project]:
    stmt = select(Project).where(Project.status != "deleted")
    if org_id:
        stmt = stmt.where(Project.org_id == org_id)
    stmt = stmt.order_by(Project.created_at.desc())
    return list(db.scalars(stmt).all())


def update_project_status(db: Session, project_id: str, status: str) -> Project | None:
    project = get_project(db, project_id)
    if project is None:
        return None
    project.status = status
    db.flush()
    return project


def update_project_status_for_org(db: Session, project_id: str, org_id: str, status: str) -> Project | None:
    project = get_project_for_org(db, project_id, org_id)
    if project is None:
        return None
    project.status = status
    db.flush()
    return project


def delete_project(db: Session, project_id: str) -> bool:
    project = db.get(Project, project_id)
    if project is None or project.status == "deleted":
        return False
    project.status = "deleted"
    db.flush()
    return True


def delete_project_for_org(db: Session, project_id: str, org_id: str) -> bool:
    project = get_project_for_org(db, project_id, org_id)
    if project is None:
        return False
    project.status = "deleted"
    db.flush()
    return True


def get_project_member(db: Session, project_id: str, user_id: str) -> ProjectMember | None:
    return db.scalar(
        select(ProjectMember)
        .options(selectinload(ProjectMember.user))
        .where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
    )


def list_project_members(db: Session, project_id: str) -> list[ProjectMember]:
    return list(
        db.scalars(
            select(ProjectMember)
            .options(selectinload(ProjectMember.user))
            .where(ProjectMember.project_id == project_id)
            .order_by(ProjectMember.created_at, ProjectMember.user_id)
        ).all()
    )


def get_active_user_for_org(db: Session, user_id: str, org_id: str) -> User | None:
    return db.scalar(
        select(User)
        .join(OrganizationMembership, OrganizationMembership.user_id == User.id)
        .where(
            User.id == user_id,
            OrganizationMembership.org_id == org_id,
            OrganizationMembership.status == "active",
            User.disabled.is_(False),
        )
    )


def count_project_members_by_role(db: Session, project_id: str, role: str) -> int:
    return int(
        db.scalar(
            select(func.count(ProjectMember.id)).where(
                ProjectMember.project_id == project_id,
                ProjectMember.role == role,
            )
        )
        or 0
    )
