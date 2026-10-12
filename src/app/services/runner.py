import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from app.auth.provider import AuthError, TokenProvider
from app.core.config import Settings
from app.google.client import GoogleClient
from app.pipeline.process import process_message
from app.pipeline.reconcile import reconcile
from app.pipeline.state import StateStore

logger = logging.getLogger(__name__)


def install_runtime(app: FastAPI, settings: Settings) -> None:
    app.state.settings = settings
    app.state.queue = asyncio.Queue(maxsize=200)
    app.state.queued = set()
    app.state.process_lock = asyncio.Lock()
    app.state.state_store = StateStore()
    app.state.http = None
    app.state.mail = None

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
    mail = GoogleClient(tokens, http, settings)
    app.state.http = http
    app.state.mail = mail
    worker = asyncio.create_task(_worker(app, mail), name="scribe-worker")
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _reconcile_job,
        "interval",
        seconds=settings.RECONCILE_INTERVAL_SECONDS,
        args=[app, mail],
        next_run_time=datetime.now(UTC) + timedelta(seconds=15),
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
        id="scribe-reconcile",
    )
    scheduler.start()
    logger.info("scribe started for %s", settings.MAILBOX_ADDRESS)
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
        await http.aclose()


async def _worker(app: FastAPI, mail: GoogleClient) -> None:
    while True:
        message_id = await app.state.queue.get()
        try:
            await process_message(
                message_id,
                mail=mail,
                state=app.state.state_store,
                settings=app.state.settings,
                lock=app.state.process_lock,
            )
        except Exception:
            logger.exception("worker failed message_id=%s", message_id)
        finally:
            app.state.queued.discard(message_id)
            app.state.queue.task_done()


async def _reconcile_job(app: FastAPI, mail: GoogleClient) -> None:
    settings: Settings = app.state.settings
    try:
        await reconcile(mail, app.state.state_store, settings, app.state.process_lock)
    except AuthError:
        logger.error("reconcile skipped; run scribe-login as %s", settings.MAILBOX_ADDRESS)
    except Exception:
        logger.exception("reconcile failed")
