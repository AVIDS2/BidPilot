from pydantic import BaseModel


class DraftSectionRequest(BaseModel):
    project_id: str
    section_key: str


class RedraftSectionRequest(BaseModel):
    project_id: str
    section_key: str
    review_feedback: str | None = None


class DraftSectionResponse(BaseModel):
    run_id: str
    status: str
