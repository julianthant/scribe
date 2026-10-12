import logging

from app.core.config import Settings
from app.graph.client import GraphClient, GraphNotFound
from app.pipeline.state import StateStore

logger = logging.getLogger(__name__)


async def ensure_subscription(graph: GraphClient, state: StateStore, settings: Settings) -> None:
    current = state.subscription_id()
    if current:
        try:
            renewed = await graph.renew_subscription(current, settings.SUBSCRIPTION_LIFETIME_DAYS)
            state.save_subscription(current, str(renewed.get("expirationDateTime") or ""))
            logger.info("renewed subscription id=%s", current)
            return
        except GraphNotFound:
            logger.info("stored subscription is gone; creating a new one")
    created = await graph.create_subscription(
        settings.GRAPH_WEBHOOK_URL,
        settings.GRAPH_CLIENT_STATE,
        settings.SUBSCRIPTION_LIFETIME_DAYS,
    )
    state.save_subscription(str(created["id"]), str(created.get("expirationDateTime") or ""))
    logger.info("created subscription id=%s", created["id"])
