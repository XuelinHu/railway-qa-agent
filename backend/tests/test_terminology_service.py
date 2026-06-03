from app.services.terminology_service import build_search_terms


def test_build_search_terms_cleans_chinese_question() -> None:
    terms = build_search_terms("牵引供电是什么意思？")

    assert "牵引供电" in terms


def test_build_search_terms_keeps_english_phrase() -> None:
    terms = build_search_terms("What is traction power supply equipment?")

    assert "traction power supply" in terms
    assert "traction" in terms
