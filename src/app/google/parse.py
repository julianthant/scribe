import base64
from datetime import UTC, datetime


def decode_b64url(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded)


def parse_gmail_message(payload: dict) -> dict:
    """Normalize a Gmail `format=full` message for the transcription pipeline."""
    headers = _headers(payload.get("payload"))
    attachments: list[dict] = []
    pending = False

    def walk(part: object) -> None:
        nonlocal pending
        if not isinstance(part, dict):
            return
        filename = part.get("filename") or ""
        body = part.get("body") if isinstance(part.get("body"), dict) else {}
        if isinstance(filename, str) and filename:
            attachment_id = body.get("attachmentId")
            inline = body.get("data")
            if isinstance(attachment_id, str) and attachment_id:
                attachments.append(
                    {
                        "id": attachment_id,
                        "name": filename,
                        "mime": str(part.get("mimeType") or ""),
                    }
                )
            elif isinstance(inline, str) and inline:
                attachments.append(
                    {
                        "id": "",
                        "name": filename,
                        "mime": str(part.get("mimeType") or ""),
                        "data": inline,
                    }
                )
            else:
                pending = True
        for child in part.get("parts") or []:
            walk(child)

    walk(payload.get("payload"))
    return {
        "id": str(payload.get("id") or ""),
        "subject": headers.get("subject", ""),
        "sender": headers.get("from", ""),
        "received_time": _received(payload.get("internalDate")),
        "attachments": attachments,
        "attachment_pending": pending and not attachments,
    }


def _headers(part: object) -> dict[str, str]:
    if not isinstance(part, dict):
        return {}
    found: dict[str, str] = {}
    for header in part.get("headers") or []:
        if not isinstance(header, dict):
            continue
        name = header.get("name")
        value = header.get("value")
        if isinstance(name, str) and isinstance(value, str):
            found[name.lower()] = value
    return found


def _received(internal_date: object) -> str:
    if not isinstance(internal_date, str) or not internal_date.isdigit():
        return ""
    return datetime.fromtimestamp(int(internal_date) / 1000, UTC).isoformat()
