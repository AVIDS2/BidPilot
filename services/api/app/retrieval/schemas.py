from pydantic import BaseModel, ConfigDict, Field

from contracts import CitationValidationStatus


class _RetrievalSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SearchRequest(_RetrievalSchema):
    project_id: str = Field(min_length=1, max_length=36)
    query: str = Field(min_length=1, max_length=4_000)
    top_k: int = Field(default=10, ge=1, le=30)


class CitationRead(_RetrievalSchema):
    source_document_id: str
    chunk_index: int
    page: int | None = None
    heading: str | None = None
    table: str | None = None
    text_anchor: str | None = None
    validation_status: CitationValidationStatus


class SearchResult(_RetrievalSchema):
    chunk_id: str
    source_document_id: str
    content: str
    score: float
    methods: tuple[str, ...]
    citation: CitationRead


class SearchResponse(_RetrievalSchema):
    project_id: str
    results: tuple[SearchResult, ...]
    degraded_reasons: tuple[str, ...] = ()
