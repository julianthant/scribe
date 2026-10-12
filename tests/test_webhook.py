import asyncio

from fastapi.testclient import TestClient

from app.api.webhook import notification_message_ids
from app.main import create_app

CLIENT_STATE = "client-state-secret-value"


def _app():
    application = create_app(start_background=False)
    application.state.settings.GRAPH_CLIENT_STATE = CLIENT_STATE
    return application


def test_validation_token_is_plain_text_and_does_no_work():
    application = _app()
    called: list[str] = []

    async def enqueue(message_id: str) -> None:
        called.append(message_id)

    application.state.enqueue = enqueue
    with TestClient(application) as client:
        response = client.post("/graph/notifications?validationToken=plain%20token")
    assert response.status_code == 200
    assert response.text == "plain token"
    assert response.headers["content-type"].startswith("text/plain")
    assert called == []


def test_mismatched_client_state_is_not_queued():
    application = _app()
    queued: list[str] = []

    async def enqueue(message_id: str) -> None:
        queued.append(message_id)

    application.state.enqueue = enqueue
    payload = {
        "value": [
            {"clientState": "wrong-state-value!!", "resourceData": {"id": "hidden"}},
            {"clientState": CLIENT_STATE, "resource": "Users/user/Messages/AAMkPath"},
            {"clientState": CLIENT_STATE, "resourceData": {"id": "AAMkData"}},
        ]
    }
    with TestClient(application) as client:
        response = client.post("/graph/notifications", json=payload)
    assert response.status_code == 202
    assert queued == ["AAMkPath", "AAMkData"]


def test_bad_json_is_still_acked():
    application = _app()
    with TestClient(application) as client:
        response = client.post(
            "/graph/notifications",
            content=b"not-json",
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 202


def test_health_names_the_mailbox():
    application = _app()
    with TestClient(application) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mailbox": "smc.scribe@outlook.com"}


def test_notification_parser_reads_both_resource_shapes():
    payload = {
        "value": [
            {"clientState": "c", "resource": "me/messages('AAMkQuoted')"},
            {"clientState": "c", "resourceData": {"id": "AAMkData"}},
            {"clientState": "other", "resourceData": {"id": "hidden"}},
        ]
    }
    assert notification_message_ids(payload, "c") == ["AAMkQuoted", "AAMkData"]


async def test_full_queue_drops_the_id_for_reconcile():
    application = _app()
    application.state.queue = asyncio.Queue(maxsize=1)
    await application.state.enqueue("one")
    await application.state.enqueue("two")
    assert application.state.queue.qsize() == 1
    assert "two" not in application.state.queued
