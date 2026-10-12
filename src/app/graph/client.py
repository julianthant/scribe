import asyncio
import base64
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx

from app.auth.provider import TokenProvider

logger = logging.getLogger(__name__)

GRAPH = "https://graph.microsoft.com/v1.0"


class GraphError(RuntimeError):
    def __init__(self, status: int, code: str) -> None:
        super().__init__(f"graph {status} {code}")
        self.status = status
        self.code = code


class GraphNotFound(GraphError):
    pass


class GraphConflict(GraphError):
    pass


class GraphClient:
    def __init__(self, tokens: TokenProvider, http: httpx.AsyncClient) -> None:
        self._tokens = tokens
        self._http = http

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        token = await _token(self._tokens)
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {token}"
        response = await self._http.request(method, url, headers=headers, **kwargs)
        if response.status_code == 401:
            token = await _token(self._tokens)
            headers["Authorization"] = f"Bearer {token}"
            response = await self._http.request(method, url, headers=headers, **kwargs)
        return response

    async def get_json(self, url: str) -> dict[str, Any]:
        response = await self._request("GET", url)
        _raise_for_status(response)
        payload = response.json()
        if not isinstance(payload, dict):
            raise GraphError(response.status_code, "invalid_json")
        return payload

    async def get_message(self, message_id: str) -> dict[str, Any]:
        select = "id,subject,receivedDateTime,from,hasAttachments"
        url = f"{GRAPH}/me/messages/{quote(message_id, safe='')}?$select={select}"
        return await self.get_json(url)

    async def list_attachments(self, message_id: str) -> list[dict[str, Any]]:
        url = f"{GRAPH}/me/messages/{quote(message_id, safe='')}/attachments?$top=50"
        items: list[dict[str, Any]] = []
        while url:
            payload = await self.get_json(url)
            values = payload.get("value", [])
            if isinstance(values, list):
                items.extend(item for item in values if isinstance(item, dict))
            next_link = payload.get("@odata.nextLink")
            url = next_link if isinstance(next_link, str) else ""
        return items

    async def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        message = quote(message_id, safe="")
        attachment = quote(attachment_id, safe="")
        url = f"{GRAPH}/me/messages/{message}/attachments/{attachment}/$value"
        response = await self._request("GET", url)
        if response.status_code == 404:
            meta = await self.get_json(f"{GRAPH}/me/messages/{message}/attachments/{attachment}")
            encoded = meta.get("contentBytes")
            if isinstance(encoded, str) and encoded:
                return base64.b64decode(encoded)
        _raise_for_status(response)
        return response.content

    async def list_inbox_since(self, since: datetime) -> list[dict[str, Any]]:
        stamp = since.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        select = "id,subject,receivedDateTime,from,hasAttachments"
        url = (
            f"{GRAPH}/me/mailFolders/inbox/messages"
            f"?$filter=receivedDateTime ge {stamp} and hasAttachments eq true"
            f"&$select={select}&$top=50"
        )
        items: list[dict[str, Any]] = []
        while url:
            payload = await self.get_json(url)
            values = payload.get("value", [])
            if isinstance(values, list):
                items.extend(item for item in values if isinstance(item, dict))
            next_link = payload.get("@odata.nextLink")
            url = next_link if isinstance(next_link, str) else ""
        return items

    async def workbook_item(self, path: str) -> dict[str, Any] | None:
        url = f"{GRAPH}/me/drive/root:/{_drive_path(path)}"
        response = await self._request("GET", url)
        if response.status_code == 404:
            return None
        _raise_for_status(response)
        payload = response.json()
        if not isinstance(payload, dict):
            raise GraphError(response.status_code, "invalid_json")
        return payload

    async def download_item(self, item_id: str) -> bytes:
        url = f"{GRAPH}/me/drive/items/{quote(item_id, safe='')}/content"
        response = await self._request("GET", url)
        _raise_for_status(response)
        return response.content

    async def upload_item(self, item_id: str, content: bytes, etag: str | None) -> None:
        headers = {
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        }
        if etag:
            headers["If-Match"] = etag
        url = f"{GRAPH}/me/drive/items/{quote(item_id, safe='')}/content"
        response = await self._request("PUT", url, headers=headers, content=content)
        if response.status_code == 412:
            raise GraphConflict(412, "precondition_failed")
        _raise_for_status(response)

    async def create_workbook(self, path: str, content: bytes) -> dict[str, Any]:
        await self._ensure_parent_folder(path)
        url = f"{GRAPH}/me/drive/root:/{_drive_path(path)}:/content"
        headers = {
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "If-None-Match": "*",
        }
        response = await self._request("PUT", url, headers=headers, content=content)
        if response.status_code == 412:
            raise GraphConflict(412, "precondition_failed")
        _raise_for_status(response)
        payload = response.json()
        if not isinstance(payload, dict):
            raise GraphError(response.status_code, "invalid_json")
        return payload

    async def _ensure_parent_folder(self, path: str) -> None:
        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        built = ""
        for segment in parent.split("/"):
            if not segment:
                continue
            if built:
                url = f"{GRAPH}/me/drive/root:/{_drive_path(built)}:/children"
            else:
                url = f"{GRAPH}/me/drive/root/children"
            body = {
                "name": segment,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "fail",
            }
            response = await self._request("POST", url, json=body)
            if response.status_code not in {200, 201, 409}:
                _raise_for_status(response)
            built = f"{built}/{segment}" if built else segment

    async def create_subscription(
        self, notification_url: str, client_state: str, lifetime_days: int
    ) -> dict[str, Any]:
        expiration = datetime.now(UTC) + timedelta(days=lifetime_days)
        body = {
            "changeType": "created",
            "notificationUrl": notification_url,
            "resource": "me/mailFolders('Inbox')/messages",
            "expirationDateTime": expiration.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "clientState": client_state,
            "latestSupportedTlsVersion": "v1_2",
        }
        response = await self._request("POST", f"{GRAPH}/subscriptions", json=body)
        _raise_for_status(response)
        payload = response.json()
        if not isinstance(payload, dict) or "id" not in payload:
            raise GraphError(response.status_code, "invalid_subscription")
        return payload

    async def renew_subscription(self, subscription_id: str, lifetime_days: int) -> dict[str, Any]:
        expiration = datetime.now(UTC) + timedelta(days=lifetime_days)
        body = {"expirationDateTime": expiration.strftime("%Y-%m-%dT%H:%M:%SZ")}
        url = f"{GRAPH}/subscriptions/{quote(subscription_id, safe='')}"
        response = await self._request("PATCH", url, json=body)
        if response.status_code == 404:
            raise GraphNotFound(404, "subscription_not_found")
        _raise_for_status(response)
        payload = response.json()
        if not isinstance(payload, dict):
            raise GraphError(response.status_code, "invalid_subscription")
        return payload


def _drive_path(path: str) -> str:
    return "/".join(quote(part, safe="") for part in path.split("/") if part)


async def _token(provider: TokenProvider) -> str:
    return await asyncio.to_thread(provider.access_token)


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    code = str(response.status_code)
    try:
        payload = response.json()
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict) and isinstance(error.get("code"), str):
                code = error["code"]
    except Exception:
        logger.info("graph error status=%s", response.status_code)
    if response.status_code == 404:
        raise GraphNotFound(response.status_code, code)
    raise GraphError(response.status_code, code)
