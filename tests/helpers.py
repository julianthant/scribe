import io
import wave
from pathlib import Path

from app.core.config import Settings


def wav_bytes(seconds: float = 1.0, rate: int = 8000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * int(rate * seconds))
    return buffer.getvalue()


def settings_for(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "GOOGLE_CLIENT_ID": "test-client-id.apps.googleusercontent.com",
        "GOOGLE_CLIENT_SECRET": "test-client-secret",
        "MAILBOX_ADDRESS": "you@gmail.com",
        "GROQ_API_KEY": "gsk-should-not-appear-in-logs",
        "WEBHOOK_SECRET": "a" * 32,
        "GOOGLE_SHEET_ID": "sheetid0123456789",
        "GOOGLE_REFRESH_TOKEN": "test-refresh-token",
        "WHISPER_MODEL_DIR": tmp_path / "models",
        "LOCAL_WHISPER_ENABLED": False,
        "MAX_ATTEMPTS": 2,
        "RETRY_BACKOFF_SECONDS": 0,
    }
    values.update(overrides)
    return Settings(**values)


def sample_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "message_id": "msg-1",
        "received_time": "2026-10-12T00:00:00Z",
        "sender": "Caller <caller@example.com>",
        "subject": "Voicemail",
        "attachment_name": "clip.wav",
        "duration_seconds": 1.0,
        "transcript": "hello",
        "model": "whisper-large-v3-turbo",
        "processed_at": "2026-10-12T00:01:00+00:00",
    }
    record.update(overrides)
    return record
