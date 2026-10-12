import logging
import re
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, Response

logger = logging.getLogger(__name__)

router = APIRouter()

# Graph resource examples:
#   Users/{user-id}/Messages/{message-id}
#   me/messages('{message-id}')
_RESOURCE_ID = re.compile(r"messages(?:\('([^']+)'\)|/([^/?]+))", re.IGNORECASE)

Enqueue = Callable[[str], Awaitable[None]]


def notification_message_ids(payload: dict, client_state: str) -> list[str]:
    values = payload.get("value")
    if not isinstance(values, list):
        return []
    ids: list[str] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        if item.get("clientState") != client_state:
            logger.warning("notification rejected because clientState did not match")
            continue
        message_id = _message_id(item)
        if message_id:
            ids.append(message_id)
    return ids


def _message_id(item: dict) -> str | None:
    resource_data = item.get("resourceData")
    if isinstance(resource_data, dict):
        message_id = resource_data.get("id")
        if isinstance(message_id, str) and message_id:
            return message_id
    resource = item.get("resource")
    if not isinstance(resource, str):
        return None
    found = list(_RESOURCE_ID.finditer(resource))
    if not found:
        return None
    match = found[-1]
    message_id = match.group(1) or match.group(2)
    if message_id:
        return message_id
    return None


@router.api_route("/graph/notifications", methods=["GET", "POST"])
async def notifications(request: Request) -> Response:
    """Graph validation must be answered immediately. Delivery is acked before work."""
    token = request.query_params.get("validationToken")
    if token is not None:
        return PlainTextResponse(token, status_code=200, media_type="text/plain")
    if request.method == "GET":
        return Response(status_code=200)
    try:
        payload = await request.json()
    except Exception:
        logger.info("notification body was not json")
        return Response(status_code=202)
    if not isinstance(payload, dict):
        return Response(status_code=202)
    settings = request.app.state.settings
    enqueue: Enqueue = request.app.state.enqueue
    for message_id in notification_message_ids(payload, settings.GRAPH_CLIENT_STATE):
        await enqueue(message_id)
    return Response(status_code=202)
