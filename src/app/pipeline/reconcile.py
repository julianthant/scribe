import logging
from datetime import UTC, datetime, timedelta

from app.core.config import Settings
from app.google.client import GoogleClient
from app.pipeline.process import process_message
from app.pipeline.state import StateStore

logger = logging.getLogger(__name__)


async def reconcile(mail: GoogleClient, state: StateStore, settings: Settings, lock) -> int:
    since = datetime.now(UTC) - timedelta(hours=settings.RECONCILE_LOOKBACK_HOURS)
    message_ids = await mail.list_pending(since)
    processed = 0
    for message_id in message_ids:
        result = await process_message(
            message_id, mail=mail, state=state, settings=settings, lock=lock
        )
        if result == "done":
            processed += 1
    logger.info("reconcile examined=%s newly_done=%s", len(message_ids), processed)
    return processed
