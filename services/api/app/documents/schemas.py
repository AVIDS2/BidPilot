from pydantic import BaseModel


class SourceDocumentRead(BaseModel):
    id: str
    bundle_id: str
    storage_key: str
    mime_type: str
    original_filename: str
    source_url: str | None
    ingest_queued: bool = False
    parse_status: str
    parse_attempt_count: int
    parser_name: str | None
    parser_version: str | None
    parse_error_code: str | None
    parse_error_detail: str | None
    parse_retryable: bool
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
