from pydantic import BaseModel


class BundleCreate(BaseModel):
    project_id: str
    label: str
    source_type: str


class BundleRead(BaseModel):
    id: str
    project_id: str
    label: str
    source_type: str
    ingest_status: str
