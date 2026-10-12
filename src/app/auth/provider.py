import threading
import time

import httpx

from app.auth.tokenstore import AuthError, load_token, save_token
from app.core.config import Settings


class TokenProvider:
    """Refresh the installed-app token. A rotated refresh token replaces the saved one."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()

    def access_token(self, force: bool = False) -> str:
        with self._lock:
            saved = load_token(self._settings.GOOGLE_TOKEN_PATH)
            refresh = (saved or {}).get("refresh_token")
            if not isinstance(refresh, str) or not refresh:
                raise AuthError(
                    "No signed-in account. Run scribe-login and sign in as "
                    f"{self._settings.MAILBOX_ADDRESS}."
                )
            access = (saved or {}).get("access_token")
            expires_at = (saved or {}).get("expires_at") or 0
            if (
                not force
                and isinstance(access, str)
                and access
                and isinstance(expires_at, int | float)
                and time.time() < float(expires_at) - 60
            ):
                return access
            refreshed = self._refresh(refresh)
            save_token(self._settings.GOOGLE_TOKEN_PATH, refreshed)
            token = refreshed["access_token"]
            if not isinstance(token, str) or not token:
                raise AuthError("Google token response did not include a usable access token.")
            return token

    def _refresh(self, refresh_token: str) -> dict:
        try:
            response = httpx.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self._settings.GOOGLE_CLIENT_ID,
                    "client_secret": self._settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=30,
            )
        except httpx.HTTPError as exc:
            raise AuthError(f"Could not refresh the Google token ({type(exc).__name__}).") from exc
        if response.status_code >= 400:
            raise AuthError(
                "Could not refresh the Google token "
                f"({_error_code(response)}). Run scribe-login again."
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise AuthError("Google token response was not JSON.")
        access = payload.get("access_token")
        if not isinstance(access, str) or not access:
            raise AuthError("Google token response did not include a usable access token.")
        rotated = payload.get("refresh_token")
        if isinstance(rotated, str) and rotated:
            refresh_token = rotated
        expires_in = payload.get("expires_in") or 3600
        try:
            ttl = int(expires_in)
        except (TypeError, ValueError):
            ttl = 3600
        return {
            "refresh_token": refresh_token,
            "access_token": access,
            "expires_at": time.time() + ttl,
        }


def _error_code(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return str(response.status_code)
    if isinstance(payload, dict) and isinstance(payload.get("error"), str):
        return payload["error"]
    return str(response.status_code)
