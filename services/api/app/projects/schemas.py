from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    scenario_package: str


class ProjectStatusUpdate(BaseModel):
    status: str


class ProjectRead(BaseModel):
    id: str
    slug: str
    name: str
    scenario_package: str
    status: str
    org_id: str = ""
    org_slug: str = ""
