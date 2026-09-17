"""Speech synthesis through edge-tts, cached on disk.

``edge-tts`` is an optional dependency imported lazily, so its absence is
reported through :func:`edge_tts_status` rather than breaking startup.

Synthesis needs the network, and the same answer is read aloud repeatedly, so
results are cached under ``SPEECH_CACHE_DIR`` keyed by voice, rate and text.
The cache is content-addressed and therefore safe to share between requests.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_missing_reason: str | None = None


class SpeechUnavailable(RuntimeError):
    """The capability was asked for but its dependency is not installed."""


@dataclass(frozen=True)
class VoiceOption:
    name: str
    label: str
    language: str
    gender: str


#: A curated list rather than a live query: these names are stable, and
#: fetching them would put a network round trip in front of every page load.
VOICES: tuple[VoiceOption, ...] = (
    VoiceOption("zh-CN-XiaoxiaoNeural", "晓晓 · 女声（默认）", "zh-CN", "Female"),
    VoiceOption("zh-CN-XiaoyiNeural", "晓伊 · 女声", "zh-CN", "Female"),
    VoiceOption("zh-CN-YunxiNeural", "云希 · 男声", "zh-CN", "Male"),
    VoiceOption("zh-CN-YunjianNeural", "云健 · 男声", "zh-CN", "Male"),
    VoiceOption("zh-CN-YunyangNeural", "云扬 · 男声（新闻）", "zh-CN", "Male"),
    VoiceOption("zh-CN-liaoning-XiaobeiNeural", "晓北 · 女声（东北）", "zh-CN", "Female"),
    VoiceOption("zh-CN-shaanxi-XiaoniNeural", "晓妮 · 女声（陕西）", "zh-CN", "Female"),
    VoiceOption("zh-HK-HiuMaanNeural", "曉曼 · 女声（粤语）", "zh-HK", "Female"),
    VoiceOption("zh-TW-HsiaoChenNeural", "曉臻 · 女声（台湾）", "zh-TW", "Female"),
    VoiceOption("en-US-AriaNeural", "Aria · English (US)", "en-US", "Female"),
    VoiceOption("en-US-GuyNeural", "Guy · English (US)", "en-US", "Male"),
)

VOICE_NAMES = frozenset(voice.name for voice in VOICES)

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


def edge_tts_status() -> dict[str, Any]:
    global _missing_reason

    if not settings.speech_tts_enabled:
        return {"available": False, "reason": "服务端语音合成已关闭"}

    if _missing_reason is None:
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            _missing_reason = (
                "服务端语音合成未安装，请执行 pip install -e '.[speech]'；"
                "浏览器内置语音不受影响"
            )

    if _missing_reason:
        return {"available": False, "reason": _missing_reason}

    return {"available": True, "default_voice": settings.speech_tts_voice}


def available_voices() -> list[VoiceOption]:
    return list(VOICES)


def _cache_path(text: str, voice: str, rate: str) -> Path:
    digest = hashlib.sha1(f"{voice}|{rate}|{text}".encode()).hexdigest()
    return Path(settings.speech_cache_dir) / f"{digest}.mp3"


async def synthesize(
    text: str,
    *,
    voice: str | None = None,
    rate: str | None = None,
) -> tuple[bytes, str]:
    """Return ``(mp3_bytes, media_type)`` for ``text``.

    Raises :class:`SpeechUnavailable` when edge-tts is absent, and the
    underlying network error when the service cannot be reached.
    """
    status = edge_tts_status()
    if not status["available"]:
        raise SpeechUnavailable(status["reason"])

    text = text.strip()
    if not text:
        raise ValueError("没有可朗读的文本")

    voice = voice or settings.speech_tts_voice
    if voice not in VOICE_NAMES:
        # An unknown name would otherwise be sent upstream and rejected with an
        # opaque error; the curated list is what the UI offers.
        raise ValueError(f"不支持的音色: {voice}")
    rate = rate or settings.speech_tts_rate

    path = _cache_path(text, voice, rate)
    if path.is_file() and path.stat().st_size > 0:
        return path.read_bytes(), "audio/mpeg"

    audio = await _synthesize_uncached(text, voice, rate)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Written under a temporary name so a concurrent reader never sees a
        # half-written file at the cache path.
        temporary = path.with_suffix(".mp3.part")
        temporary.write_bytes(audio)
        temporary.replace(path)
    except OSError:
        logger.warning("could not cache synthesized speech at %s", path, exc_info=True)

    return audio, "audio/mpeg"


async def _synthesize_uncached(text: str, voice: str, rate: str) -> bytes:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio" and chunk.get("data"):
            chunks.append(chunk["data"])

    audio = b"".join(chunks)
    if not audio:
        raise SpeechUnavailable("语音合成服务没有返回音频，请检查网络后重试")
    return audio


def cache_size_bytes() -> int:
    directory = Path(settings.speech_cache_dir)
    if not directory.is_dir():
        return 0
    return sum(item.stat().st_size for item in directory.glob("*.mp3"))
