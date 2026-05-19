from pydantic import BaseModel


class SearchRequest(BaseModel):
    project_id: str
    query: str
    top_k: int = 10
    embedding: list[float] | None = None


class SearchResult(BaseModel):
    chunk_id: str
    source_document_id: str
    content: str
    score: float
