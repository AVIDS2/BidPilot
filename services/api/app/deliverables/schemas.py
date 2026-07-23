from pydantic import BaseModel, Field


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
    sort_order: int | None = None


class DeliverableSectionUpdate(BaseModel):
    title: str | None = None
    section_key: str | None = None
    sort_order: int | None = None


class DeliverableSectionReorder(BaseModel):
    """Ordered list of section IDs — position in the list becomes sort_order."""

    section_ids: list[str] = Field(min_length=1)


class DeliverableSectionRead(BaseModel):
    id: str
    deliverable_id: str
    section_key: str
    title: str
    status: str
    sort_order: int = 0
