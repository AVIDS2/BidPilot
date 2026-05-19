from pydantic import BaseModel


class ParsedAssetRead(BaseModel):
    id: str
    source_document_id: str
    parser_name: str
    parser_version: str
    content_json: dict | None = None
    layout_json: dict | None = None
