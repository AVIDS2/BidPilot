from app.execution.deep_research import _canonical_url, _deduplicate_sources, _parse_json


def test_research_source_urls_are_stable_and_strip_fragments() -> None:
    assert _canonical_url("HTTPS://Example.com/a?b=1#section") == "https://example.com/a?b=1"
    assert _canonical_url("javascript:alert(1)") == ""


def test_research_deduplicates_sources_and_keeps_source_ids() -> None:
    sources = _deduplicate_sources(
        [
            {"query_id": "Q2", "result": {"items": [{"title": "B", "url": "https://example.com/b", "snippet": "b"}]}},
            {"query_id": "Q1", "result": {"items": [{"title": "A", "url": "https://example.com/a#top", "snippet": "a"}, {"title": "A duplicate", "url": "https://example.com/a", "snippet": "dup"}]}},
        ],
        max_sources=10,
    )
    assert [item["source_id"] for item in sources] == ["S1", "S2"]
    assert [item["url"] for item in sources] == ["https://example.com/b", "https://example.com/a"]


def test_research_json_parser_accepts_fenced_model_output() -> None:
    assert _parse_json("```json\n{\"queries\": []}\n```") == {"queries": []}
