import logging
import threading
import time

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class AuthError(RuntimeError):
    pass


class TokenProvider:
    """Refresh an access token in memory from GOOGLE_REFRESH_TOKEN.

    The refresh token lives in the Heroku config var. A replacement issued by
    Google is kept in this process only. The log names the action and never
    the credential.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._refresh_token = settings.GOOGLE_REFRESH_TOKEN
        self._access_token = ""
        self._expires_at = 0.0

    def access_token(self, force: bool = False) -> str:
        with self._lock:
            if not self._refresh_token:
                raise AuthError(
                    "No signed-in account. Run scribe-login and sign in as "
                    f"{self._settings.MAILBOX_ADDRESS}."
                )
            if not force and self._access_token and time.time() < self._expires_at - 60:
                return self._access_token
            refreshed = self._refresh(self._refresh_token)
            token = refreshed["access_token"]
            if not isinstance(token, str) or not token:
                raise AuthError("Google token response did not include a usable access token.")
            self._access_token = token
            self._expires_at = float(refreshed["expires_at"])
            rotated = refreshed["refresh_token"]
            if isinstance(rotated, str) and rotated and rotated != self._refresh_token:
                self._refresh_token = rotated
                logger.warning(
                    "Google issued a replacement credential. It stays in memory until "
                    "this process restarts. Run scribe-login again, update the Heroku "
                    "config var, and restart the dyno."
                )
            return self._access_token

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
