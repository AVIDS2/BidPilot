from datetime import datetime

from pydantic import BaseModel, Field


class DeliverableExportCreate(BaseModel):
    """Create an immutable export snapshot for the current approved content."""

    client_request_id: str | None = Field(default=None, min_length=1, max_length=128)


class ApprovedSectionSnapshotRead(BaseModel):
    deliverable_section_id: str
    section_key: str
    title: str
    section_version_id: str
    version_number: int
    content_sha256: str


class DeliverableExportRead(BaseModel):
    id: str
    project_id: str
    deliverable_id: str
    version_number: int
    status: str
    snapshot_hash: str
    approved_sections: list[ApprovedSectionSnapshotRead]
    docx_download_path: str | None
    pdf_download_path: str | None
    docx_sha256: str | None
    pdf_sha256: str | None
    failure_code: str | None
    created_at: datetime
    completed_at: datetime | None
