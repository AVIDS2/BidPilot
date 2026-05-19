from pydantic import BaseModel


class RequirementItemCreate(BaseModel):
    project_id: str
    section_key: str
    requirement_text: str
    priority: str = "normal"


class RequirementItemUpdate(BaseModel):
    requirement_text: str | None = None
    priority: str | None = None
    section_key: str | None = None
    status: str | None = None


class RequirementItemRead(BaseModel):
    id: str
    project_id: str
    section_key: str
    requirement_text: str
    priority: str
    status: str
