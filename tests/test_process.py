import asyncio
import logging

from app.google.client import GoogleNotFound
from app.pipeline.process import process_message
from app.pipeline.sheet import build_row
from app.pipeline.state import StateStore
from tests.helpers import settings_for, wav_bytes

TRANSCRIPT = "UNIQUE-TRANSCRIPT-PHRASE"


class FakeMail:
    def __init__(self) -> None:
        self.messages: dict[str, dict] = {}
        self.files: dict[str, bytes] = {}
        self.rows: list[list[object]] = []
        self.labels: list[str] = []

    async def get_message(self, message_id: str) -> dict:
        if message_id not in self.messages:
            raise GoogleNotFound(404, "notFound")
        return self.messages[message_id]

    async def download_attachment(self, message_id: str, attachment: dict) -> bytes:
        return self.files[str(attachment["id"])]

    async def sheet_contains(self, message_id: str) -> bool:
        return any(row and row[0] == message_id for row in self.rows)

    async def append_row(self, record: dict) -> bool:
        if await self.sheet_contains(str(record["message_id"])):
            return False
        self.rows.append(build_row(record))
        return True

    async def add_processed_label(self, message_id: str) -> None:
        self.labels.append(message_id)


def _message(message_id: str, attachments: list[dict] | None, *, pending: bool = False) -> dict:
    return {
        "id": message_id,
        "subject": "=1+1",
        "received_time": "2026-10-12T15:00:00+00:00",
        "sender": "Caller <caller@example.com>",
        "attachments": attachments or [],
        "attachment_pending": pending,
    }


async def test_audio_is_appended_once_labeled_and_transcript_is_not_logged(
    tmp_path, monkeypatch, caplog
):
    mail = FakeMail()
    mail.messages["msg-1"] = _message(
        "msg-1",
        [{"id": "a1", "name": "clip.wav", "mime": "audio/wav"}],
    )
    mail.files["a1"] = wav_bytes()
    calls: list[str] = []

    def fake_transcribe(path, settings):
        calls.append(path.name)
        return TRANSCRIPT, "whisper-large-v3-turbo"

    monkeypatch.setattr("app.pipeline.process.transcribe_file", fake_transcribe)
    state = StateStore()
    settings = settings_for(tmp_path)
    caplog.set_level(logging.INFO)
    lock = asyncio.Lock()
    first = await process_message("msg-1", mail=mail, state=state, settings=settings, lock=lock)
    second = await process_message("msg-1", mail=mail, state=state, settings=settings, lock=lock)
    assert first == "done"
    assert second == "skipped"
    assert calls == ["clip.wav"]
    assert state.get("msg-1") == ("done", 1)
    assert mail.labels == ["msg-1"]
    assert mail.rows[0][0] == "msg-1"
    assert mail.rows[0][2] == "Caller <caller@example.com>"
    assert mail.rows[0][3] == "'=1+1"
    assert mail.rows[0][6] == TRANSCRIPT
    assert TRANSCRIPT not in caplog.text
    assert settings.GROQ_API_KEY not in caplog.text


async def test_non_audio_is_labeled_and_skipped(tmp_path):
    mail = FakeMail()
    mail.messages["msg-2"] = _message(
        "msg-2",
        [{"id": "pdf", "name": "notes.pdf", "mime": "application/pdf"}],
    )
    state = StateStore()
    result = await process_message(
        "msg-2",
        mail=mail,
        state=state,
        settings=settings_for(tmp_path),
        lock=asyncio.Lock(),
    )
    assert result == "skipped"
    assert state.get("msg-2")[0] == "skipped"
    assert mail.rows == []
    assert mail.labels == ["msg-2"]


async def test_missing_attachment_bytes_stay_pending(tmp_path):
    mail = FakeMail()
    mail.messages["msg-3"] = _message("msg-3", [], pending=True)
    state = StateStore()
    result = await process_message(
        "msg-3",
        mail=mail,
        state=state,
        settings=settings_for(tmp_path),
        lock=asyncio.Lock(),
    )
    assert result == "pending"
    assert state.get("msg-3")[0] == "pending"
    assert mail.labels == []


async def test_deleted_message_is_skipped(tmp_path):
    state = StateStore()
    mail = FakeMail()
    result = await process_message(
        "gone",
        mail=mail,
        state=state,
        settings=settings_for(tmp_path),
        lock=asyncio.Lock(),
    )
    assert result == "skipped"
    assert state.get("gone")[0] == "skipped"
    assert mail.labels == []


async def test_failures_stop_at_max_attempts_and_get_labeled(tmp_path, monkeypatch):
    mail = FakeMail()
    mail.messages["msg-4"] = _message(
        "msg-4",
        [{"id": "a1", "name": "clip.wav", "mime": "audio/wav"}],
    )
    mail.files["a1"] = wav_bytes()
    calls = {"n": 0}

    def boom(path, settings):
        calls["n"] += 1
        raise RuntimeError("transcription failed")

    monkeypatch.setattr("app.pipeline.process.transcribe_file", boom)

    async def no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr("app.pipeline.process.asyncio.sleep", no_sleep)
    state = StateStore()
    settings = settings_for(tmp_path, MAX_ATTEMPTS=2)
    lock = asyncio.Lock()
    failed = await process_message("msg-4", mail=mail, state=state, settings=settings, lock=lock)
    again = await process_message("msg-4", mail=mail, state=state, settings=settings, lock=lock)
    assert failed == "failed"
    assert again == "skipped"
    assert calls["n"] == 2
    assert state.get("msg-4") == ("failed", 2)
    assert mail.labels == ["msg-4", "msg-4"]
