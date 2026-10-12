"""Run one inbox reconciliation. The web dyno also polls on a timer."""

import asyncio
import logging

import httpx

from app.auth.provider import TokenProvider
from app.core.config import load_settings, require_runtime
from app.core.logging import configure_logging
from app.google.client import GoogleClient
from app.pipeline.reconcile import reconcile
from app.pipeline.state import StateStore

logger = logging.getLogger(__name__)


async def run_once() -> int:
    settings = load_settings()
    require_runtime(settings)
    configure_logging(settings.LOG_LEVEL)
    state = StateStore()
    async with httpx.AsyncClient(timeout=60) as http:
        mail = GoogleClient(TokenProvider(settings), http, settings)
        lock = asyncio.Lock()
        count = await reconcile(mail, state, settings, lock)
    logger.info("poll finished newly_done=%s", count)
    return count


def main() -> None:
    asyncio.run(run_once())


if __name__ == "__main__":
    main()
