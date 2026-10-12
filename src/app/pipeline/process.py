import asyncio
import logging
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings
from app.graph.client import GraphClient, GraphNotFound
from app.pipeline.audio import duration_seconds, is_audio
from app.pipeline.excel import append_row, sheet_contains
from app.pipeline.state import StateStore
from app.pipeline.transcribe import transcribe_file

logger = logging.getLogger(__name__)


async def process_message(
    message_id: str,
    *,
    graph: GraphClient,
    state: StateStore,
    settings: Settings,
    lock: asyncio.Lock,
) -> str:
    """Process one Graph message. Returns done, skipped, pending, or failed."""
    async with lock:
        existing = state.get(message_id)
        if existing and existing[0] in {"done", "skipped"}:
            return "skipped"
        if (
            existing
            and existing[0] in {"failed", "pending"}
            and existing[1] >= settings.MAX_ATTEMPTS
        ):
            return "skipped"
        attempts = 0 if existing is None else existing[1]
        try:
            if await sheet_contains(graph, settings.ONEDRIVE_XLSX_PATH, message_id):
                state.mark(message_id, "done", attempts)
                logger.info("message_id=%s already in workbook", message_id)
                return "skipped"
        except Exception:
            logger.exception("workbook lookup failed message_id=%s", message_id)

        delay = settings.RETRY_BACKOFF_SECONDS
        while True:
            attempts += 1
            state.mark(message_id, "pending", attempts)
            try:
                outcome = await _once(message_id, graph=graph, settings=settings)
            except GraphNotFound:
                state.mark(message_id, "skipped", attempts)
                logger.info("message_id=%s not found", message_id)
                return "skipped"
            except Exception:
                state.mark(message_id, "failed", attempts)
                logger.exception("message_id=%s attempt=%s failed", message_id, attempts)
                if attempts >= settings.MAX_ATTEMPTS:
                    return "failed"
                await asyncio.sleep(min(delay, 60))
                delay *= 2
                continue
            if outcome == "pending":
                logger.info("message_id=%s attachments not listed yet", message_id)
                return "pending"
            if outcome == "skipped":
                state.mark(message_id, "skipped", attempts)
                logger.info("message_id=%s has no audio attachment", message_id)
                return "skipped"
            state.mark(message_id, "done", attempts)
            logger.info("message_id=%s processed", message_id)
            return "done"


async def _once(message_id: str, *, graph: GraphClient, settings: Settings) -> str:
    message = await graph.get_message(message_id)
    attachments = await graph.list_attachments(message_id)
    audio = [
        item
        for item in attachments
        if item.get("@odata.type", "#microsoft.graph.fileAttachment").endswith("fileAttachment")
        and is_audio(str(item.get("name") or ""), item.get("contentType"))
    ]
    if not audio:
        if message.get("hasAttachments") and not attachments:
            return "pending"
        return "skipped"

    names: list[str] = []
    transcripts: list[str] = []
    models: list[str] = []
    total_duration = 0.0
    with tempfile.TemporaryDirectory() as directory:
        workdir = Path(directory)
        for item in audio:
            name = str(item.get("name") or "audio")
            content = await graph.download_attachment(message_id, str(item["id"]))
            path = workdir / Path(name).name
            path.write_bytes(content)
            total_duration += await asyncio.to_thread(duration_seconds, path)
            text, model = await asyncio.to_thread(transcribe_file, path, settings)
            names.append(name)
            transcripts.append(text)
            models.append(model)

    sender = _sender(message)
    record = {
        "message_id": message_id,
        "received_time": str(message.get("receivedDateTime") or ""),
        "sender": sender,
        "subject": str(message.get("subject") or ""),
        "attachment_name": "; ".join(names),
        "duration_seconds": round(total_duration, 1),
        "transcript": "\n".join(transcripts),
        "model": ",".join(dict.fromkeys(models)),
        "processed_at": datetime.now(UTC).isoformat(),
    }
    await append_row(graph, settings.ONEDRIVE_XLSX_PATH, record)
    return "done"


def _sender(message: dict) -> str:
    email = message.get("from") or {}
    if isinstance(email, dict):
        address = email.get("emailAddress") or {}
        if isinstance(address, dict):
            name = str(address.get("name") or "")
            mailbox = str(address.get("address") or "")
            if name and mailbox:
                return f"{name} <{mailbox}>"
            return name or mailbox
    return ""
