import asyncio
import logging
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx

from app.auth.provider import TokenProvider
from app.core.config import Settings
from app.google.parse import decode_b64url, parse_gmail_message
from app.pipeline.sheet import (
    HEADERS,
    SheetFormatError,
    build_row,
    header_matches,
    message_ids_from_column,
)

logger = logging.getLogger(__name__)

GMAIL = "https://gmail.googleapis.com/gmail/v1"
SHEETS = "https://sheets.googleapis.com/v4"


class GoogleError(RuntimeError):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(f"google {status} {code}")
        self.status = status
        self.code = code


class GoogleNotFound(GoogleError):
    pass


class GoogleClient:
    def __init__(self, tokens: TokenProvider, http: httpx.AsyncClient, settings: Settings) -> None:
        self._tokens = tokens
        self._http = http
        self._settings = settings
        self._label_id: str | None = None

    async def get_message(self, message_id: str) -> dict[str, Any]:
        url = f"{GMAIL}/users/me/messages/{quote(message_id, safe='')}?format=full"
        payload = await self.get_json(url)
        parsed = parse_gmail_message(payload)
        parsed["id"] = message_id
        return parsed

    async def download_attachment(self, message_id: str, attachment: dict[str, Any]) -> bytes:
        inline = attachment.get("data")
        if isinstance(inline, str) and inline:
            return decode_b64url(inline)
        attachment_id = attachment.get("id")
        if not isinstance(attachment_id, str) or not attachment_id:
            raise GoogleError(400, "missing_attachment")
        url = (
            f"{GMAIL}/users/me/messages/{quote(message_id, safe='')}"
            f"/attachments/{quote(attachment_id, safe='')}"
        )
        payload = await self.get_json(url)
        data = payload.get("data")
        if not isinstance(data, str) or not data:
            raise GoogleError(502, "missing_attachment_data")
        return decode_b64url(data)

    async def list_pending(self, since: datetime) -> list[str]:
        label = self._settings.GMAIL_LABEL.replace('"', "")
        query = (
            "has:attachment (filename:mp3 OR filename:wav OR filename:wave) "
            f'-label:"{label}" after:{int(since.timestamp())} -in:spam -in:trash'
        )
        params: dict[str, str] = {"q": query, "maxResults": "50"}
        ids: list[str] = []
        while True:
            payload = await self.get_json(f"{GMAIL}/users/me/messages", params=params)
            for item in payload.get("messages") or []:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    ids.append(item["id"])
            page = payload.get("nextPageToken")
            if not isinstance(page, str) or not page:
                return ids
            params["pageToken"] = page

    async def sheet_contains(self, message_id: str) -> bool:
        values = await self._column_a()
        return message_id in message_ids_from_column(values)

    async def append_row(self, record: dict[str, Any]) -> bool:
        """Append one row. Returns False when the message id is already present."""
        header = await self._header_row()
        if header and not header_matches(header):
            raise SheetFormatError("Google Sheet header does not match Scribe columns")
        if await self.sheet_contains(str(record["message_id"])):
            logger.info("sheet already has message_id=%s", record["message_id"])
            return False
        if not header:
            await self._write_header()
        await self._append(build_row(record))
        logger.info(
            "appended message_id=%s model=%s duration=%s",
            record["message_id"],
            record["model"],
            record["duration_seconds"],
        )
        return True

    async def add_processed_label(self, message_id: str) -> None:
        label_id = await self._processed_label_id()
        url = f"{GMAIL}/users/me/messages/{quote(message_id, safe='')}/modify"
        await self._json("POST", url, json={"addLabelIds": [label_id]})
        logger.info("labeled message_id=%s", message_id)

    async def get_json(self, url: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        response = await self._request("GET", url, params=params)
        _raise_for_status(response)
        payload = response.json()
        if not isinstance(payload, dict):
            raise GoogleError(response.status_code, "invalid_json")
        return payload

    async def _processed_label_id(self) -> str:
        if self._label_id:
            return self._label_id
        payload = await self.get_json(f"{GMAIL}/users/me/labels")
        name = self._settings.GMAIL_LABEL
        for label in payload.get("labels") or []:
            if isinstance(label, dict) and label.get("name") == name and label.get("id"):
                self._label_id = str(label["id"])
                return self._label_id
        try:
            created = await self._json(
                "POST",
                f"{GMAIL}/users/me/labels",
                json={
                    "name": name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
        except GoogleError as exc:
            if exc.status != 409:
                raise
            payload = await self.get_json(f"{GMAIL}/users/me/labels")
            for label in payload.get("labels") or []:
                if isinstance(label, dict) and label.get("name") == name and label.get("id"):
                    self._label_id = str(label["id"])
                    return self._label_id
            raise
        label_id = created.get("id")
        if not isinstance(label_id, str) or not label_id:
            raise GoogleError(502, "missing_label")
        self._label_id = label_id
        return label_id

    async def _column_a(self) -> list:
        payload = await self._values(f"{self._settings.GOOGLE_SHEET_TAB}!A:A")
        values = payload.get("values")
        return values if isinstance(values, list) else []

    async def _header_row(self) -> list | None:
        payload = await self._values(f"{self._settings.GOOGLE_SHEET_TAB}!A1:I1")
        values = payload.get("values")
        if not isinstance(values, list) or not values:
            return None
        row = values[0]
        return row if isinstance(row, list) else None

    async def _values(self, cell_range: str) -> dict[str, Any]:
        sheet_id = quote(self._settings.GOOGLE_SHEET_ID, safe="")
        encoded = quote(cell_range, safe="")
        url = f"{SHEETS}/spreadsheets/{sheet_id}/values/{encoded}"
        response = await self._request("GET", url)
        _raise_for_status(response)
        payload = response.json()
        if not isinstance(payload, dict):
            raise GoogleError(response.status_code, "invalid_json")
        return payload

    async def _write_header(self) -> None:
        cell_range = f"{self._settings.GOOGLE_SHEET_TAB}!A1:I1"
        await self._values_update(cell_range, [HEADERS], "RAW")

    async def _append(self, row: list[object]) -> None:
        cell_range = f"{self._settings.GOOGLE_SHEET_TAB}!A:I"
        sheet_id = quote(self._settings.GOOGLE_SHEET_ID, safe="")
        encoded = quote(cell_range, safe="")
        url = (
            f"{SHEETS}/spreadsheets/{sheet_id}/values/{encoded}:append"
            "?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS"
        )
        await self._json("POST", url, json={"values": [row]})

    async def _values_update(self, cell_range: str, rows: list, option: str) -> None:
        sheet_id = quote(self._settings.GOOGLE_SHEET_ID, safe="")
        encoded = quote(cell_range, safe="")
        url = f"{SHEETS}/spreadsheets/{sheet_id}/values/{encoded}?valueInputOption={option}"
        await self._json(
            "PUT",
            url,
            json={"range": cell_range, "majorDimension": "ROWS", "values": rows},
        )

    async def _json(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        response = await self._request(method, url, **kwargs)
        _raise_for_status(response)
        if not response.content:
            return {}
        payload = response.json()
        if not isinstance(payload, dict):
            raise GoogleError(response.status_code, "invalid_json")
        return payload

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        token = await asyncio.to_thread(self._tokens.access_token)
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {token}"
        response = await self._http.request(method, url, headers=headers, **kwargs)
        if response.status_code == 401:
            token = await asyncio.to_thread(self._tokens.access_token, True)
            headers["Authorization"] = f"Bearer {token}"
            response = await self._http.request(method, url, headers=headers, **kwargs)
        return response


def _error_code(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return str(response.status_code)
    if not isinstance(payload, dict):
        return str(response.status_code)
    error = payload.get("error")
    if isinstance(error, str):
        return error
    if isinstance(error, dict):
        status = error.get("status")
        if isinstance(status, str):
            return status
        code = error.get("code")
        if code is not None:
            return str(code)
    return str(response.status_code)


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    code = _error_code(response)
    logger.info("google error status=%s code=%s", response.status_code, code)
    if response.status_code == 404:
        raise GoogleNotFound(response.status_code, code)
    raise GoogleError(response.status_code, code)
