import asyncio
import logging
from io import BytesIO

from openpyxl import load_workbook
from tests.helpers import settings_for, wav_bytes

from app.graph.client import GraphNotFound
from app.pipeline.process import process_message
from app.pipeline.state import StateStore

TRANSCRIPT = "UNIQUE-TRANSCRIPT-PHRASE"


class FakeGraph:
    def __init__(self) -> None:
        self.messages: dict[str, dict] = {}
        self.attachments: dict[str, list[dict]] = {}
        self.files: dict[str, bytes] = {}
        self.workbook: bytes | None = None

    async def get_message(self, message_id: str) -> dict:
        if message_id not in self.messages:
            raise GraphNotFound(404, "ErrorItemNotFound")
        return self.messages[message_id]

    async def list_attachments(self, message_id: str) -> list[dict]:
        return list(self.attachments.get(message_id, []))

    async def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        return self.files[attachment_id]

    async def workbook_item(self, path: str) -> dict | None:
        if self.workbook is None:
            return None
        return {"id": "wb", "eTag": "etag-1"}

    async def download_item(self, item_id: str) -> bytes:
        assert self.workbook is not None
        return self.workbook

    async def upload_item(self, item_id: str, content: bytes, etag: str | None) -> None:
        self.workbook = content

    async def create_workbook(self, path: str, content: bytes) -> dict:
        self.workbook = content
        return {"id": "wb"}


def _message(message_id: str, *, attachments: bool) -> dict:
    return {
        "id": message_id,
        "subject": "=1+1",
        "receivedDateTime": "2026-10-12T15:00:00Z",
        "hasAttachments": attachments,
        "from": {"emailAddress": {"name": "Caller", "address": "caller@example.com"}},
    }


async def test_audio_is_appended_once_and_transcript_is_not_logged(tmp_path, monkeypatch, caplog):
    graph = FakeGraph()
    graph.messages["msg-1"] = _message("msg-1", attachments=True)
    graph.attachments["msg-1"] = [
        {
            "id": "a1",
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": "clip.wav",
            "contentType": "audio/wav",
        }
    ]
    graph.files["a1"] = wav_bytes()
    calls: list[str] = []

    def fake_transcribe(path, settings):
        calls.append(path.name)
        return TRANSCRIPT, "whisper-large-v3-turbo"

    monkeypatch.setattr("app.pipeline.process.transcribe_file", fake_transcribe)
    state = StateStore(tmp_path / "scribe.db")
    settings = settings_for(tmp_path)
    caplog.set_level(logging.INFO)
    lock = asyncio.Lock()
    first = await process_message("msg-1", graph=graph, state=state, settings=settings, lock=lock)
    second = await process_message("msg-1", graph=graph, state=state, settings=settings, lock=lock)
    assert first == "done"
    assert second == "skipped"
    assert calls == ["clip.wav"]
    assert state.get("msg-1") == ("done", 1)
    assert graph.workbook is not None
    sheet = load_workbook(BytesIO(graph.workbook)).active
    assert sheet["A2"].value == "msg-1"
    assert sheet["C2"].value == "Caller <caller@example.com>"
    assert sheet["D2"].value == "'=1+1"
    assert sheet["G2"].value == TRANSCRIPT
    assert TRANSCRIPT not in caplog.text
    assert settings.GROQ_API_KEY not in caplog.text


async def test_non_audio_is_skipped(tmp_path):
    graph = FakeGraph()
    graph.messages["msg-2"] = _message("msg-2", attachments=True)
    graph.attachments["msg-2"] = [
        {
            "id": "pdf",
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": "notes.pdf",
            "contentType": "application/pdf",
        }
    ]
    state = StateStore(tmp_path / "scribe.db")
    result = await process_message(
        "msg-2",
        graph=graph,
        state=state,
        settings=settings_for(tmp_path),
        lock=asyncio.Lock(),
    )
    assert result == "skipped"
    assert state.get("msg-2")[0] == "skipped"
    assert graph.workbook is None


async def test_missing_attachment_list_stays_pending(tmp_path):
    graph = FakeGraph()
    graph.messages["msg-3"] = _message("msg-3", attachments=True)
    state = StateStore(tmp_path / "scribe.db")
    result = await process_message(
        "msg-3",
        graph=graph,
        state=state,
        settings=settings_for(tmp_path),
        lock=asyncio.Lock(),
    )
    assert result == "pending"
    assert state.get("msg-3")[0] == "pending"


async def test_deleted_message_is_skipped(tmp_path):
    state = StateStore(tmp_path / "scribe.db")
    result = await process_message(
        "gone",
        graph=FakeGraph(),
        state=state,
        settings=settings_for(tmp_path),
        lock=asyncio.Lock(),
    )
    assert result == "skipped"
    assert state.get("gone")[0] == "skipped"


async def test_failures_stop_at_max_attempts(tmp_path, monkeypatch):
    graph = FakeGraph()
    graph.messages["msg-4"] = _message("msg-4", attachments=True)
    graph.attachments["msg-4"] = [
        {
            "id": "a1",
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": "clip.wav",
            "contentType": "audio/wav",
        }
    ]
    graph.files["a1"] = wav_bytes()
    calls = {"n": 0}

    def boom(path, settings):
        calls["n"] += 1
        raise RuntimeError("transcription failed")

    monkeypatch.setattr("app.pipeline.process.transcribe_file", boom)

    async def no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr("app.pipeline.process.asyncio.sleep", no_sleep)
    state = StateStore(tmp_path / "scribe.db")
    settings = settings_for(tmp_path, MAX_ATTEMPTS=2)
    lock = asyncio.Lock()
    failed = await process_message("msg-4", graph=graph, state=state, settings=settings, lock=lock)
    again = await process_message("msg-4", graph=graph, state=state, settings=settings, lock=lock)
    assert failed == "failed"
    assert again == "skipped"
    assert calls["n"] == 2
    assert state.get("msg-4") == ("failed", 2)
