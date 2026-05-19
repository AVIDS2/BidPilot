from pydantic import BaseModel


class DeliverableCreate(BaseModel):
    project_id: str
    type: str
    title: str


class DeliverableRead(BaseModel):
    id: str
    project_id: str
    type: str
    title: str
    status: str
    export_status: str


class DeliverableSectionCreate(BaseModel):
    deliverable_id: str
    section_key: str
    title: str


class DeliverableSectionRead(BaseModel):
    id: str
    deliverable_id: str
    section_key: str
    title: str
    status: str
