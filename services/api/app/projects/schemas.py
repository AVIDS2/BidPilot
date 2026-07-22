from typing import Literal

from pydantic import BaseModel


ProjectRole = Literal["owner", "manager", "contributor", "reviewer", "viewer"]


class ProjectCreate(BaseModel):
    name: str
    scenario_package: str


class ProjectStatusUpdate(BaseModel):
    status: Literal["active", "archived"]


class ProjectRead(BaseModel):
    id: str
    slug: str
    name: str
    scenario_package: str
    status: str
    org_id: str = ""
    org_slug: str = ""


class ProjectMemberCreate(BaseModel):
    user_id: str
    role: ProjectRole = "contributor"


class ProjectMemberUpdate(BaseModel):
    role: ProjectRole


class ProjectMemberRead(BaseModel):
    user_id: str
    display_name: str
    role: ProjectRole
    source: Literal["membership"] = "membership"
