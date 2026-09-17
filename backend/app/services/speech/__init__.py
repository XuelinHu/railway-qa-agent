"""Server-side speech, used when the browser cannot do the job itself.

The web UI prefers the platform's own speech APIs and only falls back to these
providers. That fallback is genuinely optional, so every dependency here is
imported lazily and its absence is a reported capability rather than a startup
failure: ``pip install -e '.[speech]'`` turns it on.
"""

from app.services.speech.asr import transcribe_audio, whisper_status
from app.services.speech.tts import (
    VoiceOption,
    available_voices,
    edge_tts_status,
    synthesize,
)

__all__ = [
    "VoiceOption",
    "available_voices",
    "edge_tts_status",
    "synthesize",
    "transcribe_audio",
    "whisper_status",
]
