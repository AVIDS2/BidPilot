from pydantic import BaseModel


class SourceDocumentRead(BaseModel):
    id: str
    bundle_id: str
    storage_key: str
    mime_type: str
    original_filename: str
    parse_status: str


class DocumentsPaginatedResponse(BaseModel):
    items: list[SourceDocumentRead]
    total: int
    page: int
    page_size: int
    pages: int
