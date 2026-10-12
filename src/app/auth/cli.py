"""One-time device-code login for the Outlook.com mailbox."""

import sys

from msal import PublicClientApplication

from app.auth.cache import load_cache, save_cache
from app.auth.scopes import SCOPES
from app.core.config import load_settings


def main() -> None:
    settings = load_settings()
    cache = load_cache(settings.TOKEN_CACHE_PATH)
    client = PublicClientApplication(
        settings.MS_CLIENT_ID,
        authority=settings.MS_AUTHORITY,
        token_cache=cache,
    )
    flow = client.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        message = flow.get("error_description") or flow.get("error") or "device code flow failed"
        print(f"Login failed: {message}", file=sys.stderr)
        raise SystemExit(1)
    print(flow["message"])
    print(f"Sign in as {settings.MAILBOX_ADDRESS}.")
    result = client.acquire_token_by_device_flow(flow)
    if not result or "access_token" not in result:
        code = (result or {}).get("error") or "device_code_failed"
        print(f"Login failed ({code}).", file=sys.stderr)
        raise SystemExit(1)
    save_cache(settings.TOKEN_CACHE_PATH, cache)
    print(f"Signed in. Token cache saved to {settings.TOKEN_CACHE_PATH} (mode 600).")


if __name__ == "__main__":
    main()
