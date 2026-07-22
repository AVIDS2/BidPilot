from app.retrieval.normalization import NORMALIZER_VERSION, normalize_retrieval_text


def test_normalizer_adds_cjk_bigrams_and_preserves_structured_terms() -> None:
    normalized = normalize_retrieval_text("投标文件必须支持云平台部署，符合 ISO 27001。")
    terms = normalized.split()

    assert NORMALIZER_VERSION == "bidpilot-lexical-v1"
    assert "云平" in terms
    assert "平台" in terms
    assert "iso" in terms
    assert "27001" in terms


def test_normalizer_normalizes_whitespace_and_case() -> None:
    assert normalize_retrieval_text("  Cloud\tDeployment\nAWS  ") == "cloud deployment aws"
