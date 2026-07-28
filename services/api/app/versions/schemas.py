from pydantic import BaseModel


class SectionVersionRead(BaseModel):
    id: str
    deliverable_section_id: str
    version_number: int
    content_markdown: str | None = None
    created_by_actor: str
    generation_run_id: str | None = None
    evidence_set_id: str | None = None
    response_plan_section_id: str | None = None
    response_plan_evidence_binding_id: str | None = None
