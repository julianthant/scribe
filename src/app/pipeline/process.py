import asyncio
import logging
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings
from app.google.client import GoogleClient, GoogleNotFound
from app.pipeline.audio import duration_seconds, is_audio
from app.pipeline.state import StateStore
from app.pipeline.transcribe import transcribe_file

logger = logging.getLogger(__name__)


async def process_message(
    message_id: str,
    *,
    mail: GoogleClient,
    state: StateStore,
    settings: Settings,
    lock: asyncio.Lock,
) -> str:
    """Process one Gmail message. Returns done, skipped, pending, or failed."""
    async with lock:
        existing = state.get(message_id)
        if existing and existing[0] in {"done", "skipped"}:
            return "skipped"
        if (
            existing
            and existing[0] in {"failed", "pending"}
            and existing[1] >= settings.MAX_ATTEMPTS
        ):
            await _label_quiet(mail, message_id)
            return "skipped"
        attempts = 0 if existing is None else existing[1]
        delay = settings.RETRY_BACKOFF_SECONDS
        while True:
            attempts += 1
            state.mark(message_id, "pending", attempts)
            try:
                if await mail.sheet_contains(message_id):
                    await _label_or_missing(mail, message_id)
                    state.mark(message_id, "done", attempts)
                    logger.info("message_id=%s already in sheet", message_id)
                    return "skipped"
                outcome = await _once(message_id, mail=mail, settings=settings)
                if outcome == "pending":
                    logger.info("message_id=%s attachments not listed yet", message_id)
                    return "pending"
                if outcome == "skipped":
                    await _label_or_missing(mail, message_id)
                    state.mark(message_id, "skipped", attempts)
                    logger.info("message_id=%s has no audio attachment", message_id)
                    return "skipped"
                await _label_or_missing(mail, message_id)
                state.mark(message_id, "done", attempts)
                logger.info("message_id=%s processed", message_id)
                return "done"
            except GoogleNotFound:
                state.mark(message_id, "skipped", attempts)
                logger.info("message_id=%s not found", message_id)
                return "skipped"
            except Exception:
                state.mark(message_id, "failed", attempts)
                logger.exception("message_id=%s attempt=%s failed", message_id, attempts)
                if attempts >= settings.MAX_ATTEMPTS:
                    await _label_quiet(mail, message_id)
                    return "failed"
                await asyncio.sleep(min(delay, 60))
                delay *= 2
                continue


async def _label_or_missing(mail: GoogleClient, message_id: str) -> None:
    try:
        await mail.add_processed_label(message_id)
    except GoogleNotFound:
        logger.info("message_id=%s not found while labeling", message_id)


async def _label_quiet(mail: GoogleClient, message_id: str) -> None:
    try:
        await mail.add_processed_label(message_id)
    except Exception:
        logger.exception("label failed message_id=%s", message_id)


async def _once(message_id: str, *, mail: GoogleClient, settings: Settings) -> str:
    message = await mail.get_message(message_id)
    attachments = message.get("attachments") or []
    audio = [
        item for item in attachments if is_audio(str(item.get("name") or ""), item.get("mime"))
    ]
    if not audio:
        if message.get("attachment_pending"):
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
            content = await mail.download_attachment(message_id, item)
            path = workdir / Path(name).name
            path.write_bytes(content)
            total_duration += await asyncio.to_thread(duration_seconds, path)
            text, model = await asyncio.to_thread(transcribe_file, path, settings)
            names.append(name)
            transcripts.append(text)
            models.append(model)

    record = {
        "message_id": message_id,
        "received_time": str(message.get("received_time") or ""),
        "sender": str(message.get("sender") or ""),
        "subject": str(message.get("subject") or ""),
        "attachment_name": "; ".join(names),
        "duration_seconds": round(total_duration, 1),
        "transcript": "\n".join(transcripts),
        "model": ",".join(dict.fromkeys(models)),
        "processed_at": datetime.now(UTC).isoformat(),
    }
    await mail.append_row(record)
    return "done"
