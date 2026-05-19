from pydantic import BaseModel


class EvidenceRead(BaseModel):
    id: str
    project_id: str
    source_document_id: str
    quote_text: str
    confidence: float | None = None


class KnowledgeChunkRead(BaseModel):
    id: str
    project_id: str
    source_document_id: str
    chunk_index: int
    content: str
    metadata_json: dict | None = None
