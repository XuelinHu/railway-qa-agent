"""Speech endpoints, the fallback path for browsers without native support.

The web UI asks :func:`capabilities` once and only calls these when it has to.
Both capabilities are optional at install time, so every endpoint reports a
missing dependency as 503 with an actionable message instead of failing in a
way that looks like a bug.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import CurrentPrincipal
from app.core.config import settings
from app.services.speech import (
    available_voices,
    edge_tts_status,
    synthesize,
    transcribe_audio,
    whisper_status,
)
from app.services.speech.asr import SpeechUnavailable as ASRUnavailable
from app.services.speech.tts import SpeechUnavailable as TTSUnavailable

logger = logging.getLogger(__name__)

router = APIRouter()

#: Push-to-talk clips are seconds long; this is a guard against a runaway
#: upload rather than a real limit anyone should reach.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

UNAVAILABLE = status.HTTP_503_SERVICE_UNAVAILABLE


class VoiceRead(BaseModel):
    name: str
    label: str
    language: str
    gender: str


class CapabilityRead(BaseModel):
    available: bool
    reason: str | None = None
    model: str | None = None
    device: str | None = None
    default_voice: str | None = None


class CapabilitiesResponse(BaseModel):
    #: Whether the browser must call /transcribe, i.e. the server can do it.
    asr: CapabilityRead
    tts: CapabilityRead
    voices: list[VoiceRead] = Field(default_factory=list)


class TranscribeResponse(BaseModel):
    text: str
    language: str | None = None
    duration: float | None = None


class SynthesizeRequest(BaseModel):
    #: Bounded by SPEECH_TTS_MAX_CHARS: reading a whole manual aloud is never
    #: what the caller wants, and it would hold a synthesis request open.
    text: str = Field(min_length=1)
    voice: str | None = None
    rate: str | None = Field(default=None, pattern=r"^[+-]\d{1,3}%$")


def _to_read(voice) -> VoiceRead:
    return VoiceRead(
        name=voice.name,
        label=voice.label,
        language=voice.language,
        gender=voice.gender,
    )


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def capabilities(_: CurrentPrincipal) -> CapabilitiesResponse:
    """What the server can do, so the client knows whether to fall back."""
    asr = whisper_status()
    tts = edge_tts_status()
    return CapabilitiesResponse(
        asr=CapabilityRead(**asr),
        tts=CapabilityRead(**tts),
        voices=[_to_read(voice) for voice in available_voices()],
    )


@router.get("/voices", response_model=list[VoiceRead])
async def list_voices(_: CurrentPrincipal) -> list[VoiceRead]:
    return [_to_read(voice) for voice in available_voices()]


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    _: CurrentPrincipal,
    file: Annotated[UploadFile, File(description="录音文件（webm/wav/mp3 等）")],
    language: str | None = None,
) -> TranscribeResponse:
    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="录音为空")
    if len(audio) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"录音过大，请控制在 {MAX_UPLOAD_BYTES // 1024 // 1024}MB 以内",
        )

    try:
        result = await transcribe_audio(
            audio, language=language, filename=file.filename
        )
    except ASRUnavailable as exc:
        raise HTTPException(status_code=UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - decoding failures are caller-facing
        logger.exception("transcription failed")
        raise HTTPException(status_code=502, detail=f"语音识别失败: {exc}") from exc

    if not result.text:
        raise HTTPException(status_code=422, detail="没有识别到语音内容，请靠近麦克风重试")

    return TranscribeResponse(
        text=result.text, language=result.language, duration=result.duration
    )


@router.post("/synthesize")
async def synthesize_speech(
    payload: SynthesizeRequest,
    _: CurrentPrincipal,
) -> Response:
    """Return mp3 audio for ``payload.text``."""
    if len(payload.text) > settings.speech_tts_max_chars:
        raise HTTPException(
            status_code=413,
            detail=f"文本过长，请控制在 {settings.speech_tts_max_chars} 字以内",
        )

    try:
        audio, media_type = await synthesize(
            payload.text, voice=payload.voice, rate=payload.rate
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TTSUnavailable as exc:
        raise HTTPException(status_code=UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - upstream failures are caller-facing
        logger.exception("synthesis failed")
        raise HTTPException(status_code=502, detail=f"语音合成失败: {exc}") from exc

    return Response(content=audio, media_type=media_type)
