import asyncio
import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app.api.webhook import signature_matches
from app.main import create_app

SECRET = "client-state-secret-value"


def _app():
    application = create_app(start_background=False)
    application.state.settings.WEBHOOK_SECRET = SECRET
    return application


def _signed(payload: dict) -> tuple[bytes, str]:
    body = json.dumps(payload, separators=(",", ":")).encode()
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return body, digest


def test_valid_signature_enqueues_the_message_id():
    application = _app()
    queued: list[str] = []

    async def enqueue(message_id: str) -> None:
        queued.append(message_id)

    application.state.enqueue = enqueue
    body, digest = _signed({"message_id": "18f4abc"})
    with TestClient(application) as client:
        response = client.post(
            "/gmail/notifications",
            content=body,
            headers={"content-type": "application/json", "X-Scribe-Signature": digest},
        )
    assert response.status_code == 202
    assert queued == ["18f4abc"]


def test_bad_signature_is_rejected_and_not_queued():
    application = _app()
    queued: list[str] = []

    async def enqueue(message_id: str) -> None:
        queued.append(message_id)

    application.state.enqueue = enqueue
    body, _digest = _signed({"message_id": "18f4abc"})
    with TestClient(application) as client:
        response = client.post(
            "/gmail/notifications",
            content=body,
            headers={"content-type": "application/json", "X-Scribe-Signature": "0" * 64},
        )
    assert response.status_code == 401
    assert queued == []


def test_signed_garbage_is_acked_without_enqueue():
    application = _app()
    queued: list[str] = []

    async def enqueue(message_id: str) -> None:
        queued.append(message_id)

    application.state.enqueue = enqueue
    body = b"not-json"
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    with TestClient(application) as client:
        response = client.post(
            "/gmail/notifications",
            content=body,
            headers={"X-Scribe-Signature": f"sha256={digest}"},
        )
    assert response.status_code == 202
    assert queued == []
    assert signature_matches(SECRET, body, f"sha256={digest}")


def test_health_names_the_mailbox():
    application = _app()
    with TestClient(application) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mailbox": "you@gmail.com"}


async def test_full_queue_drops_the_id_for_reconcile():
    application = _app()
    application.state.queue = asyncio.Queue(maxsize=1)
    await application.state.enqueue("one")
    await application.state.enqueue("two")
    assert application.state.queue.qsize() == 1
    assert "two" not in application.state.queued
