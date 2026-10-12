import logging
import tempfile
import threading
from pathlib import Path

import httpx

from app.core.config import Settings
from app.pipeline.audio import prepare_for_groq

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()


class TranscriptionError(RuntimeError):
    pass


class GroqError(TranscriptionError):
    pass


def transcribe_file(path: Path, settings: Settings) -> tuple[str, str]:
    try:
        with tempfile.TemporaryDirectory() as directory:
            parts = prepare_for_groq(path, Path(directory))
            texts = [_groq(part, settings) for part in parts]
        text = " ".join(part for part in texts if part).strip()
        return text, settings.GROQ_MODEL
    except GroqError:
        logger.info("groq transcription failed; trying local faster-whisper")
        text = _local(path, settings)
        return text, f"faster-whisper-{settings.WHISPER_MODEL}"


def _groq(path: Path, settings: Settings) -> str:
    if not settings.GROQ_API_KEY:
        raise GroqError("missing_api_key")
    try:
        with path.open("rb") as handle:
            response = httpx.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                data={"model": settings.GROQ_MODEL},
                files={"file": (path.name, handle, "application/octet-stream")},
                timeout=180,
            )
    except httpx.HTTPError as exc:
        raise GroqError(type(exc).__name__) from exc
    if response.status_code >= 400:
        raise GroqError(str(response.status_code))
    payload = response.json()
    text = payload.get("text") if isinstance(payload, dict) else None
    if not isinstance(text, str):
        raise GroqError("missing_text")
    return text.strip()


def _local(path: Path, settings: Settings) -> str:
    if not settings.LOCAL_WHISPER_ENABLED:
        raise TranscriptionError("local whisper is disabled and Groq failed")
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise TranscriptionError(
            "faster-whisper is not installed. Install scribe with the local extra."
        ) from exc
    global _model
    with _model_lock:
        if _model is None:
            settings.WHISPER_MODEL_DIR.mkdir(parents=True, exist_ok=True)
            _model = WhisperModel(
                settings.WHISPER_MODEL,
                device="cpu",
                compute_type="int8",
                download_root=str(settings.WHISPER_MODEL_DIR),
            )
        model = _model
    segments, _info = model.transcribe(str(path), language="en")
    return " ".join(segment.text.strip() for segment in segments).strip()
