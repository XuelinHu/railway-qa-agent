import re

ZH_PATTERN = re.compile(r"[\u4e00-\u9fff]")


def detect_language(text: str) -> str:
    return "zh" if ZH_PATTERN.search(text) else "en"

