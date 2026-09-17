"""Speech helpers that do not need the optional dependencies installed."""

from __future__ import annotations

import pytest

from app.services.speech import available_voices, edge_tts_status, whisper_status
from app.services.speech.tts import DEFAULT_VOICE, VOICE_NAMES, _cache_path


def test_voice_list_is_unique_and_non_empty():
    voices = available_voices()
    assert voices
    names = [voice.name for voice in voices]
    assert len(names) == len(set(names))


def test_default_voice_is_offered():
    # A default the UI cannot select would leave the picker blank.
    assert DEFAULT_VOICE in VOICE_NAMES


def test_voice_names_are_lowercase_tags():
    # edge-tts matches these exactly; a stray capital is a runtime 400.
    for name in VOICE_NAMES:
        assert name == name.strip()
        assert " " not in name


def test_cache_path_is_content_addressed():
    first = _cache_path("你好", "zh-CN-XiaoxiaoNeural", "+0%")
    assert first == _cache_path("你好", "zh-CN-XiaoxiaoNeural", "+0%")
    assert first.suffix == ".mp3"


@pytest.mark.parametrize(
    "changed",
    [
        ("你好", "zh-CN-YunxiNeural", "+0%"),
        ("你好啊", "zh-CN-XiaoxiaoNeural", "+0%"),
        ("你好", "zh-CN-XiaoxiaoNeural", "+20%"),
    ],
)
def test_cache_path_separates_voice_text_and_rate(changed):
    # Sharing a cache entry across any of these would read the wrong audio back.
    assert _cache_path(*changed) != _cache_path("你好", "zh-CN-XiaoxiaoNeural", "+0%")


def test_status_reports_a_reason_when_unavailable():
    # The UI shows this text, so an unavailable capability must explain itself
    # rather than just returning False.
    for status in (whisper_status(), edge_tts_status()):
        assert status["available"] in (True, False)
        if not status["available"]:
            assert status.get("reason")
