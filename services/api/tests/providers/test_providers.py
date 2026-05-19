from app.providers.llm import generate
from app.providers.parser import parse


def test_llm_generate_stub() -> None:
    result = generate("Write a technical approach section")
    assert result.text.startswith("[stub]")
    assert result.model == "default"


def test_parser_parse_stub() -> None:
    result = parse("uploads/test.pdf", "application/pdf")
    assert len(result.pages) >= 1
    assert result.parser_name == "stub"
    assert result.mime_type == "application/pdf"
