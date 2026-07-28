from pydantic import BaseModel


class SourceDocumentRead(BaseModel):
    id: str
    bundle_id: str
    storage_key: str
    mime_type: str
    original_filename: str
    parse_status: str
    parse_attempt_count: int
    parse_error_code: str | None
    index_status: str
    index_error_code: str | None
    version_number: int
    supersedes_document_id: str | None


class DocumentsPaginatedResponse(BaseModel):
    items: list[SourceDocumentRead]
    total: int
    page: int
    page_size: int
    pages: int
