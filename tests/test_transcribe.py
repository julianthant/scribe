import logging
from pathlib import Path

import httpx
import pytest
from tests.helpers import settings_for, wav_bytes

from app.pipeline.transcribe import TranscriptionError, transcribe_file


def _wav(tmp_path: Path) -> Path:
    path = tmp_path / "clip.wav"
    path.write_bytes(wav_bytes())
    return path


def test_groq_429_falls_back_to_local_without_logging_secrets(tmp_path, monkeypatch, caplog):
    secret = "TRANSCRIPT-BODY-SHOULD-NOT-LOG"
    api_key = "gsk-should-not-appear-in-logs"
    settings = settings_for(tmp_path, GROQ_API_KEY=api_key, LOCAL_WHISPER_ENABLED=True)

    def fake_post(*args, **kwargs):
        class Response:
            status_code = 429
            text = secret

            def json(self):
                return {"error": {"message": secret}}

        return Response()

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(
        "app.pipeline.transcribe._local",
        lambda path, settings: "local words",
    )
    caplog.set_level(logging.INFO)
    text, model = transcribe_file(_wav(tmp_path), settings)
    assert text == "local words"
    assert model == "faster-whisper-small"
    assert secret not in caplog.text
    assert api_key not in caplog.text


def test_groq_failure_without_local_raises(tmp_path, monkeypatch):
    settings = settings_for(tmp_path, LOCAL_WHISPER_ENABLED=False)

    def fake_post(*args, **kwargs):
        class Response:
            status_code = 500
            text = "upstream"

            def json(self):
                return {}

        return Response()

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(TranscriptionError):
        transcribe_file(_wav(tmp_path), settings)
