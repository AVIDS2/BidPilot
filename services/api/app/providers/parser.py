"""Parser adapter — abstracts document parsing behind a thin interface.

Current implementation: stub that returns placeholder parsed output.
Future: call PDF/DOCX parsers, OCR, etc.
"""

from dataclasses import dataclass


@dataclass
class ParsedPage:
    page_number: int
    text: str
    layout: dict | None = None


@dataclass
class ParseResult:
    pages: list[ParsedPage]
    mime_type: str
    parser_name: str = "stub"


def parse(storage_key: str, mime_type: str) -> ParseResult:
    """Parse a document from storage. Stub implementation."""
    return ParseResult(
        pages=[ParsedPage(page_number=1, text="[stub] Parsed content")],
        mime_type=mime_type,
        parser_name="stub",
    )
