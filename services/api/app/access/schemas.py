from dataclasses import dataclass

from app.models import Project, ProjectMember


@dataclass(frozen=True)
class ProjectAccess:
    project: Project
    effective_role: str
    membership: ProjectMember | None
    used_admin_bypass: bool
