import threading

from msal import PublicClientApplication

from app.auth.cache import load_cache, save_cache
from app.auth.scopes import SCOPES
from app.core.config import Settings


class AuthError(RuntimeError):
    pass


class TokenProvider:
    """Silent token acquisition. The cache file is rewritten when MSAL rotates the refresh token."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()

    def access_token(self) -> str:
        with self._lock:
            cache = load_cache(self._settings.TOKEN_CACHE_PATH)
            client = PublicClientApplication(
                self._settings.MS_CLIENT_ID,
                authority=self._settings.MS_AUTHORITY,
                token_cache=cache,
            )
            accounts = client.get_accounts()
            if not accounts:
                raise AuthError(
                    "No signed-in account. Run scribe-login and sign in as "
                    f"{self._settings.MAILBOX_ADDRESS}."
                )
            result = client.acquire_token_silent(SCOPES, account=accounts[0])
            if not result or "access_token" not in result:
                code = (result or {}).get("error") or "silent_auth_failed"
                raise AuthError(
                    f"Could not refresh the Microsoft token ({code}). Run scribe-login again."
                )
            if cache.has_state_changed:
                save_cache(self._settings.TOKEN_CACHE_PATH, cache)
            token = result["access_token"]
            if not isinstance(token, str) or not token:
                raise AuthError("Microsoft token response did not include a usable access token.")
            return token
