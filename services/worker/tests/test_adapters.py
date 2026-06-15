"""Tests for worker adapters: parser, embedding, LLM, requirements, export."""

import os
import tempfile

from app.adapters.parser import _extract_text, _split_into_chunks, ParsedChunk, store_chunks
from app.adapters import embedding as embedding_adapter
from app.adapters import llm as llm_adapter
from app.adapters import requirements as requirements_adapter
from app.adapters.embedding import generate_embedding, generate_embeddings_batch
from app.adapters.llm import draft_section
from app.adapters.requirements import extract_requirements
from app.adapters.export import render_markdown_to_docx, _parse_markdown_to_blocks


class TestParserChunking:
    def test_split_empty_text(self) -> None:
        assert _split_into_chunks("") == []
        assert _split_into_chunks("   ") == []

    def test_split_short_text_returns_single_chunk(self) -> None:
        text = "Short paragraph."
        chunks = _split_into_chunks(text)
        assert len(chunks) == 1
        content, meta = chunks[0]
        assert content == "Short paragraph."
        assert meta["chunk_type"] == "paragraphs"
        assert isinstance(meta["heading_path"], list)

    def test_split_heading_boundaries(self) -> None:
        text = "# Section 1\n\nPara one.\n\n## Sub 1.1\n\nPara two."
        chunks = _split_into_chunks(text)
        assert len(chunks) >= 2
        # Each chunk should have heading_path reflecting its section
        paths = [meta["heading_path"] for _, meta in chunks]
        assert any("Section 1" in p for p in paths)
        assert any("Sub 1.1" in p for p in paths)

    def test_table_atomic(self) -> None:
        text = "# Data\n\n| Name | Value |\n|------|-------|\n| A    | 1     |\n| B    | 2     |"
        chunks = _split_into_chunks(text)
        table_chunks = [(c, m) for c, m in chunks if m["chunk_type"] == "table"]
        assert len(table_chunks) >= 1
        _, meta = table_chunks[0]
        assert meta["table_headers"] == ["Name", "Value"]
        assert meta["table_row_count"] == 2

    def test_heading_path_tracking(self) -> None:
        text = "# Level 1\n\n## Level 2\n\n### Level 3\n\nContent here."
        chunks = _split_into_chunks(text)
        assert len(chunks) >= 1
        _, meta = chunks[-1]
        assert "Level 3" in meta["heading_path"]
        assert "Level 2" in meta["heading_path"]
        assert "Level 1" in meta["heading_path"]

    def test_long_text_multiple_chunks(self) -> None:
        paragraphs = [f"Paragraph {i} with some content here for testing purposes." for i in range(50)]
        text = "\n\n".join(paragraphs)
        chunks = _split_into_chunks(text, size=200)
        assert len(chunks) > 1

    def test_extract_text_plain_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("Hello world from plain text file.")
            path = f.name
        try:
            result = _extract_text(path, "text/plain")
            assert "Hello world" in result
        finally:
            os.unlink(path)


class TestEmbeddingAdapter:
    def test_stub_embedding_without_api_key(self) -> None:
        # Ensure no API key is set
        os.environ.pop("EMBEDDING_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("DOCPILOT_PROVIDER_OPENAI_API_KEY", None)
        os.environ.pop("DOCPILOT_PROVIDER_DOMESTIC_API_KEY", None)
        os.environ.pop("ALIYUN_API_KEY", None)
        os.environ.pop("DASHSCOPE_API_KEY", None)
        result = generate_embedding("test text")
        assert result.model == "stub"
        assert len(result.embedding) == 1536
        assert all(v == 0.0 for v in result.embedding)

    def test_batch_stub_without_api_key(self) -> None:
        os.environ.pop("EMBEDDING_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("DOCPILOT_PROVIDER_OPENAI_API_KEY", None)
        os.environ.pop("DOCPILOT_PROVIDER_DOMESTIC_API_KEY", None)
        os.environ.pop("ALIYUN_API_KEY", None)
        os.environ.pop("DASHSCOPE_API_KEY", None)
        results = generate_embeddings_batch(["text1", "text2"])
        assert len(results) == 2
        assert all(r.model == "stub" for r in results)

    def test_domestic_embedding_env_uses_dashscope_defaults(self, monkeypatch) -> None:
        monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
        monkeypatch.delenv("EMBEDDING_API_URL", raising=False)
        monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DOCPILOT_PROVIDER_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DOCPILOT_PROVIDER_DOMESTIC_BASE_URL", raising=False)
        monkeypatch.delenv("DOCPILOT_PROVIDER_DOMESTIC_API_KEY", raising=False)
        monkeypatch.delenv("DOCPILOT_EMBEDDING_MODEL_TEXT", raising=False)
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        monkeypatch.setenv("ALIYUN_API_KEY", "test-aliyun-key")

        assert embedding_adapter._api_key() == "test-aliyun-key"
        assert embedding_adapter._api_url() == "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
        assert embedding_adapter._api_model() == "text-embedding-v4"


class TestLLMAdapter:
    def test_stub_draft_without_api_key(self) -> None:
        os.environ.pop("LLM_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("DOCPILOT_PROVIDER_OPENAI_API_KEY", None)
        os.environ.pop("DOCPILOT_PROVIDER_DOMESTIC_API_KEY", None)
        os.environ.pop("ALIYUN_API_KEY", None)
        os.environ.pop("DASHSCOPE_API_KEY", None)
        result = draft_section("technical-approach", ["evidence text"], "proj1")
        assert result.model_used == "stub"
        assert "technical-approach" in result.content_markdown.lower() or "Technical Approach" in result.content_markdown
        assert "evidence text" in result.content_markdown

    def test_domestic_llm_env_uses_dashscope_defaults(self, monkeypatch) -> None:
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_URL", raising=False)
        monkeypatch.delenv("LLM_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DOCPILOT_PROVIDER_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DOCPILOT_PROVIDER_DOMESTIC_BASE_URL", raising=False)
        monkeypatch.delenv("DOCPILOT_PROVIDER_DOMESTIC_API_KEY", raising=False)
        monkeypatch.delenv("DOCPILOT_LLM_MODEL_PRIMARY", raising=False)
        monkeypatch.delenv("ALIYUN_API_KEY", raising=False)
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-dashscope-key")

        assert llm_adapter._api_key() == "test-dashscope-key"
        assert llm_adapter._api_url() == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        assert llm_adapter._api_model() == "qwen3.5-flash"


class TestProviderEnv:
    def test_requirements_adapter_uses_domestic_chat_config(self, monkeypatch) -> None:
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_URL", raising=False)
        monkeypatch.delenv("LLM_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DOCPILOT_PROVIDER_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ALIYUN_API_KEY", raising=False)
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        monkeypatch.setenv("DOCPILOT_PROVIDER_DOMESTIC_API_KEY", "test-domestic-key")
        monkeypatch.setenv("DOCPILOT_PROVIDER_DOMESTIC_BASE_URL", "https://example.test/v1/")
        monkeypatch.setenv("DOCPILOT_LLM_MODEL_PRIMARY", "qwen-test")

        assert requirements_adapter._api_key() == "test-domestic-key"
        assert requirements_adapter._api_url() == "https://example.test/v1/chat/completions"
        assert requirements_adapter._api_model() == "qwen-test"


class TestRequirementsAdapter:
    def test_stub_extracts_shall_must(self) -> None:
        os.environ.pop("LLM_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        chunks = [
            "The system shall provide user authentication.\nUsers must change passwords every 90 days.",
            "The interface should be responsive.",
            "This is just a description with no requirements.",
        ]
        results = extract_requirements(chunks, "proj1")
        assert len(results) >= 2
        assert any("shall" in r.requirement_text.lower() or "must" in r.requirement_text.lower() for r in results)
        # High priority for shall/must
        high = [r for r in results if r.priority == "high"]
        assert len(high) >= 1


class TestExportAdapter:
    def test_parse_markdown_blocks(self) -> None:
        md = "# Title\n\n## Subtitle\n\nParagraph text\n\n- Bullet 1\n- Bullet 2\n\n1. Numbered item"
        blocks = _parse_markdown_to_blocks(md)
        types = [b["type"] for b in blocks]
        assert "h1" in types
        assert "h2" in types
        assert "paragraph" in types
        assert "bullet" in types
        assert "numbered" in types

    def test_render_docx_returns_bytes(self) -> None:
        sections = [
            {"title": "Section 1", "content_markdown": "## Heading\n\nSome text here.\n\n- Item A\n- Item B"},
            {"title": "Section 2", "content_markdown": "Another section with **bold** text."},
        ]
        result = render_markdown_to_docx(sections)
        assert isinstance(result, bytes)
        assert len(result) > 100  # DOCX should be non-trivial
        # Verify it's a valid ZIP (DOCX is a ZIP archive)
        import zipfile
        buf = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
        buf.write(result)
        buf.close()
        try:
            assert zipfile.is_zipfile(buf.name)
        finally:
            os.unlink(buf.name)
