from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Project


def create_project(db: Session, project: Project) -> Project:
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_project(db: Session, project_id: str) -> Project | None:
    return db.get(Project, project_id)


def get_project_for_org(db: Session, project_id: str, org_id: str) -> Project | None:
    stmt = select(Project).where(Project.id == project_id, Project.org_id == org_id)
    return db.scalar(stmt)


def list_projects(db: Session, org_id: str | None = None) -> list[Project]:
    stmt = select(Project)
    if org_id:
        stmt = stmt.where(Project.org_id == org_id)
    stmt = stmt.order_by(Project.created_at.desc())
    return list(db.scalars(stmt).all())


def update_project_status(db: Session, project_id: str, status: str) -> Project | None:
    project = db.get(Project, project_id)
    if project is None:
        return None
    project.status = status
    db.commit()
    db.refresh(project)
    return project


def update_project_status_for_org(db: Session, project_id: str, org_id: str, status: str) -> Project | None:
    project = get_project_for_org(db, project_id, org_id)
    if project is None:
        return None
    project.status = status
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project_id: str) -> bool:
    project = db.get(Project, project_id)
    if project is None:
        return False
    db.delete(project)
    db.commit()
    return True


def delete_project_for_org(db: Session, project_id: str, org_id: str) -> bool:
    project = get_project_for_org(db, project_id, org_id)
    if project is None:
        return False
    db.delete(project)
    db.commit()
    return True
