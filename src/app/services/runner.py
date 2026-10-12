import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.auth.provider import AuthError, TokenProvider
from app.core.config import Settings
from app.graph.client import GraphClient
from app.pipeline.process import process_message
from app.pipeline.reconcile import reconcile
from app.pipeline.state import StateStore
from app.pipeline.subscription import ensure_subscription

logger = logging.getLogger(__name__)


def install_runtime(app: FastAPI, settings: Settings) -> None:
    app.state.settings = settings
    app.state.queue = asyncio.Queue(maxsize=200)
    app.state.queued = set()
    app.state.process_lock = asyncio.Lock()
    app.state.state_store = StateStore(settings.STATE_DB_PATH)
    app.state.http = None
    app.state.graph = None

    async def enqueue(message_id: str) -> None:
        if message_id in app.state.queued:
            return
        app.state.queued.add(message_id)
        try:
            app.state.queue.put_nowait(message_id)
        except asyncio.QueueFull:
            app.state.queued.discard(message_id)
            logger.warning("queue full; reconcile will retry message_id=%s", message_id)

    app.state.enqueue = enqueue


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    if not getattr(app.state, "start_background", True):
        yield
        return
    http = httpx.AsyncClient(timeout=60)
    tokens = TokenProvider(settings)
    graph = GraphClient(tokens, http)
    app.state.http = http
    app.state.graph = graph
    tasks = [
        asyncio.create_task(_worker(app, graph), name="scribe-worker"),
        asyncio.create_task(_subscription_loop(app, graph), name="scribe-subscription"),
        asyncio.create_task(_reconcile_loop(app, graph), name="scribe-reconcile"),
    ]
    logger.info("scribe started for %s", settings.MAILBOX_ADDRESS)
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await http.aclose()


async def _worker(app: FastAPI, graph: GraphClient) -> None:
    while True:
        message_id = await app.state.queue.get()
        try:
            await process_message(
                message_id,
                graph=graph,
                state=app.state.state_store,
                settings=app.state.settings,
                lock=app.state.process_lock,
            )
        except Exception:
            logger.exception("worker failed message_id=%s", message_id)
        finally:
            app.state.queued.discard(message_id)
            app.state.queue.task_done()


async def _subscription_loop(app: FastAPI, graph: GraphClient) -> None:
    settings: Settings = app.state.settings
    while True:
        try:
            await ensure_subscription(graph, app.state.state_store, settings)
            await asyncio.sleep(settings.SUBSCRIPTION_RENEW_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            raise
        except AuthError:
            logger.error("subscription skipped; run scribe-login as %s", settings.MAILBOX_ADDRESS)
            await asyncio.sleep(300)
        except Exception:
            logger.exception("subscription renew failed")
            await asyncio.sleep(300)


async def _reconcile_loop(app: FastAPI, graph: GraphClient) -> None:
    settings: Settings = app.state.settings
    while True:
        try:
            await reconcile(graph, app.state.state_store, settings, app.state.process_lock)
        except asyncio.CancelledError:
            raise
        except AuthError:
            logger.error("reconcile skipped; run scribe-login as %s", settings.MAILBOX_ADDRESS)
        except Exception:
            logger.exception("reconcile failed")
        await asyncio.sleep(settings.RECONCILE_INTERVAL_SECONDS)
