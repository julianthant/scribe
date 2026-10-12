import hashlib
import hmac
import json
import logging
import re

from fastapi import APIRouter, Request
from fastapi.responses import Response

logger = logging.getLogger(__name__)

router = APIRouter()

_MESSAGE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_MAX_BODY = 4096


def signature_matches(secret: str, body: bytes, header: str | None) -> bool:
    if not header:
        return False
    provided = header.removeprefix("sha256=").strip()
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)


@router.post("/gmail/notifications")
async def notifications(request: Request) -> Response:
    """Ack a signed Apps Script ping before any Gmail or transcription work."""
    body = await request.body()
    if len(body) > _MAX_BODY:
        return Response(status_code=413)
    settings = request.app.state.settings
    header = request.headers.get("x-scribe-signature")
    if not signature_matches(settings.WEBHOOK_SECRET, body, header):
        logger.warning("notification rejected because the signature did not match")
        return Response(status_code=401)
    message_id = _message_id(body)
    if message_id is None:
        logger.info("notification ignored")
        return Response(status_code=202)
    await request.app.state.enqueue(message_id)
    return Response(status_code=202)


def _message_id(body: bytes) -> str | None:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    message_id = payload.get("message_id")
    if not isinstance(message_id, str) or _MESSAGE_ID.fullmatch(message_id) is None:
        return None
    return message_id
