from app.services.language import detect_language


def test_detect_language_zh() -> None:
    assert detect_language("牵引供电设备如何维护？") == "zh"


def test_detect_language_en() -> None:
    assert detect_language("How should traction power equipment be maintained?") == "en"

