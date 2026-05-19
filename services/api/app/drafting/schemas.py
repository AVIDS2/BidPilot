from pydantic import BaseModel


class DraftSectionRequest(BaseModel):
    project_id: str
    section_key: str
    provider_config_id: str | None = None


class RedraftSectionRequest(BaseModel):
    project_id: str
    section_key: str
    review_feedback: str | None = None
    provider_config_id: str | None = None


class DraftSectionResponse(BaseModel):
    run_id: str
    status: str
