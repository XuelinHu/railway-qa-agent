"""Speech recognition through faster-whisper.

``faster-whisper`` is an optional dependency, so it is imported inside the
function that needs it. Transcription is CPU-bound and synchronous, so it runs
in a worker thread to keep the event loop free.

The model is held in memory between requests because reloading it costs
seconds, and released again after ``SPEECH_ASR_IDLE_UNLOAD_SECONDS`` so a host
that is short of memory gets it back without a restart.
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

#: Set once the package is found to be missing, so the import is not retried on
#: every request.
_missing_reason: str | None = None


class SpeechUnavailable(RuntimeError):
    """The capability was asked for but its dependency is not installed."""


@dataclass
class Transcript:
    text: str
    language: str | None = None
    duration: float | None = None


class _WhisperPool:
    """Holds the loaded model and a timer that releases it when idle."""

    def __init__(self) -> None:
        self._model: Any = None
        self._lock = asyncio.Lock()
        self._last_used = 0.0
        self._reaper: asyncio.Task | None = None

    @property
    def loaded(self) -> bool:
        return self._model is not None

    async def get(self) -> Any:
        async with self._lock:
            if self._model is None:
                self._model = await asyncio.to_thread(self._load)
                logger.info(
                    "loaded whisper model %s on %s",
                    settings.speech_asr_model,
                    settings.speech_asr_device,
                )
            self._last_used = time.monotonic()
            self._ensure_reaper()
            return self._model

    def _load(self) -> Any:
        from faster_whisper import WhisperModel

        return WhisperModel(
            settings.speech_asr_model,
            device=settings.speech_asr_device,
            compute_type=settings.speech_asr_compute_type,
            cpu_threads=settings.speech_asr_cpu_threads,
        )

    def _ensure_reaper(self) -> None:
        if self._reaper is None or self._reaper.done():
            self._reaper = asyncio.create_task(self._reap_when_idle())

    async def _reap_when_idle(self) -> None:
        """Release the model once nothing has used it for a while.

        A single long sleep beats polling: the deadline is only ever pushed
        further out by a request, never brought forward.
        """
        interval = max(settings.speech_asr_idle_unload_seconds, 60)
        try:
            while True:
                idle_for = time.monotonic() - self._last_used
                if idle_for < interval:
                    await asyncio.sleep(interval - idle_for)
                    continue
                async with self._lock:
                    if self._model is not None and time.monotonic() - self._last_used >= interval:
                        self._model = None
                        logger.info("released the whisper model after %ds idle", interval)
                return
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            raise


_pool = _WhisperPool()


def whisper_status() -> dict[str, Any]:
    """Whether server-side transcription can run, and why not when it cannot."""
    global _missing_reason

    if not settings.speech_asr_enabled:
        return {"available": False, "reason": "服务端语音识别已关闭"}

    if _missing_reason is None:
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            _missing_reason = (
                "服务端语音识别未安装，请执行 pip install -e '.[speech]'；"
                "浏览器支持语音识别时不受影响"
            )

    if _missing_reason:
        return {"available": False, "reason": _missing_reason}

    return {
        "available": True,
        "model": settings.speech_asr_model,
        "device": settings.speech_asr_device,
    }


async def transcribe_audio(
    audio: bytes,
    *,
    language: str | None = None,
    filename: str | None = None,
) -> Transcript:
    """Transcribe ``audio``, raising :class:`SpeechUnavailable` when it cannot."""
    status = whisper_status()
    if not status["available"]:
        raise SpeechUnavailable(status["reason"])

    model = await _pool.get()
    segments, info = await asyncio.to_thread(
        _run, model, audio, language, filename
    )
    text = " ".join(segment for segment in segments if segment).strip()
    return Transcript(
        text=text,
        language=getattr(info, "language", None),
        duration=getattr(info, "duration", None),
    )


def _run(model: Any, audio: bytes, language: str | None, filename: str | None):
    """Blocking transcription, executed in a worker thread.

    ``vad_filter`` drops the silence that push-to-talk recordings are full of,
    which both speeds this up and stops whisper inventing words for it.
    """
    buffer = io.BytesIO(audio)
    buffer.name = filename or "audio.webm"
    segments, info = model.transcribe(
        buffer,
        language=language,
        beam_size=5,
        vad_filter=True,
    )
    return [segment.text.strip() for segment in segments], info
