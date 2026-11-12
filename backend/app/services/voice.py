"""Optional local offline Speech-to-Text (STT) fallback using faster-whisper."""

from __future__ import annotations

import logging
import os
import tempfile
from functools import lru_cache

from ..config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_whisper_model(model_name: str):
    from faster_whisper import WhisperModel  # type: ignore[import-not-found]

    return WhisperModel(model_name, device="cpu", compute_type="int8")


def transcribe_audio_local(
    audio_bytes: bytes,
    *,
    content_type: str | None = None,
) -> tuple[str | None, str | None]:
    """Transcribe audio locally when enabled and faster-whisper is installed.

    Returns (transcript, detected_language) or (None, None) on any unavailability
    or failure so report persistence is never blocked.
    """
    if not settings.local_stt_enabled or not audio_bytes:
        return None, None

    ext_map = {
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/mp4": ".m4a",
        "audio/x-m4a": ".m4a",
    }
    base_type = (content_type or "").split(";")[0].strip().lower()
    suffix = ext_map.get(base_type, ".wav")

    temp_path: str | None = None
    try:
        model = _load_whisper_model(settings.local_stt_model)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            temp_path = tmp.name

        segments, info = model.transcribe(temp_path, beam_size=1)
        transcript = " ".join(seg.text.strip() for seg in segments if seg.text.strip()).strip()
        if not transcript:
            return None, None
        language = getattr(info, "language", None)
        return transcript[:1200], (str(language) if language else None)
    except ImportError:
        logger.info("LOCAL_STT_ENABLED=true, but faster-whisper is not installed.")
        return None, None
    except Exception as exc:
        logger.warning("Local STT fallback failed: %s", type(exc).__name__)
        return None, None
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

