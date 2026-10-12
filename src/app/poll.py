"""Run one inbox reconciliation. Used by hand and by the backup GitHub Actions workflow."""

import asyncio
import logging

import httpx

from app.auth.provider import TokenProvider
from app.core.config import load_settings, require_runtime
from app.core.logging import configure_logging
from app.graph.client import GraphClient
from app.pipeline.reconcile import reconcile
from app.pipeline.state import StateStore

logger = logging.getLogger(__name__)


async def run_once() -> int:
    settings = load_settings()
    require_runtime(settings)
    configure_logging(settings.LOG_LEVEL)
    state = StateStore(settings.STATE_DB_PATH)
    async with httpx.AsyncClient(timeout=60) as http:
        graph = GraphClient(TokenProvider(settings), http)
        lock = asyncio.Lock()
        count = await reconcile(graph, state, settings, lock)
    logger.info("poll finished newly_done=%s", count)
    return count


def main() -> None:
    asyncio.run(run_once())


if __name__ == "__main__":
    main()
