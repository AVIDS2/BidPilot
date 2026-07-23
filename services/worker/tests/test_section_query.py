"""Unit tests for bilingual section-key retrieval query expansion."""

from app.retrieval.section_query import expand_section_retrieval_query, section_fallback_query


def test_expand_technical_approach_includes_chinese_keywords() -> None:
    query = expand_section_retrieval_query("technical-approach")
    assert "technical approach" in query
    assert "技术方案" in query
    assert "架构" in query


def test_expand_unknown_section_keeps_english_tokens() -> None:
    query = expand_section_retrieval_query("custom-risk-matrix")
    assert query == "custom risk matrix"


def test_fallback_query_is_chinese_for_known_sections() -> None:
    fallback = section_fallback_query("technical-approach")
    assert "技术方案" in fallback
    assert "technical" not in fallback
