import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Project

from .repository import create_project, get_project, list_projects, update_project_status, delete_project
from .schemas import ProjectCreate, ProjectRead


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


def create_project_command(db: Session, payload: ProjectCreate, org_id: str) -> ProjectRead:
    base_slug = _slugify(payload.name)
    slug = _unique_slug(db, base_slug)
    project = Project(
        name=payload.name,
        slug=slug,
        scenario_package=payload.scenario_package,
        org_id=org_id,
    )
    project = create_project(db, project)

    # Auto-create deliverable and sections from scenario template
    if project.scenario_package:
        try:
            from app.scenarios.templates import get_sections_for_scenario
            from app.models import Deliverable, DeliverableSection

            sections = get_sections_for_scenario(project.scenario_package)
            if sections:
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
                db.commit()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Failed to auto-create sections: %s", exc)
            db.rollback()

    return _project_to_read(project)


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


def list_projects_query(db: Session, org_id: str | None = None) -> list[ProjectRead]:
    projects = list_projects(db, org_id)
    return [_project_to_read(p) for p in projects]


def update_project_status_command(db: Session, project_id: str, status: str) -> ProjectRead | None:
    project = update_project_status(db, project_id, status)
    if project is None:
        return None
    return _project_to_read(project)


def delete_project_command(db: Session, project_id: str) -> bool:
    return delete_project(db, project_id)
