import logging
from datetime import UTC, datetime, timedelta

from app.core.config import Settings
from app.graph.client import GraphClient
from app.pipeline.process import process_message
from app.pipeline.state import StateStore

logger = logging.getLogger(__name__)


async def reconcile(graph: GraphClient, state: StateStore, settings: Settings, lock) -> int:
    since = datetime.now(UTC) - timedelta(hours=settings.RECONCILE_LOOKBACK_HOURS)
    messages = await graph.list_inbox_since(since)
    processed = 0
    for message in messages:
        message_id = message.get("id")
        if not isinstance(message_id, str):
            continue
        result = await process_message(
            message_id, graph=graph, state=state, settings=settings, lock=lock
        )
        if result == "done":
            processed += 1
    logger.info("reconcile examined=%s newly_done=%s", len(messages), processed)
    return processed
