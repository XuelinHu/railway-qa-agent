from app.rag.terminology_extractor import extract_pairs_from_line


def test_extract_pairs_from_mixed_line() -> None:
    pairs = extract_pairs_from_line(
        "安全/安全性 safety 安全措施 safeguard 安全带 safety belt"
    )

    assert ("安全/安全性", "safety") in pairs
    assert ("安全措施", "safeguard") in pairs
    assert ("安全带", "safety belt") in pairs


def test_extract_pairs_normalizes_cjk_spaces() -> None:
    pairs = extract_pairs_from_line("标 引 indexing;designation 标 志 indicator;sign;marker")

    assert ("标引", "indexing;designation") in pairs
    assert ("标志", "indicator;sign;marker") in pairs
