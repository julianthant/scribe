"""One-time installed-app login for the Gmail mailbox."""

import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from app.auth.scopes import SCOPES
from app.core.config import ConfigError, load_settings


def main() -> None:
    settings = load_settings()
    if not settings.GOOGLE_CLIENT_SECRET:
        raise ConfigError("Configuration error:\n  GOOGLE_CLIENT_SECRET is required")
    if not settings.MAILBOX_ADDRESS:
        raise ConfigError("Configuration error:\n  MAILBOX_ADDRESS is required")
    redirect = f"http://127.0.0.1:{settings.SCRIBE_OAUTH_PORT}/"
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "login_hint": settings.MAILBOX_ADDRESS,
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    print(f"Open this URL and sign in as {settings.MAILBOX_ADDRESS}:")
    print(auth_url)
    print("This command runs on your laptop. The browser redirects to this machine.")
    code = _wait_for_code(settings.SCRIBE_OAUTH_HOST, settings.SCRIBE_OAUTH_PORT)
    token = _exchange(settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET, redirect, code)
    email = _profile(str(token["access_token"]))
    if email.casefold() != settings.MAILBOX_ADDRESS.casefold():
        print(f"Signed in as {email}. Expected {settings.MAILBOX_ADDRESS}.", file=sys.stderr)
        raise SystemExit(1)
    refresh = str(token["refresh_token"])
    print(f"Signed in as {email}.")
    print("Do not commit this value or paste it into a log, ticket, or chat.")
    print("Set it on the Heroku app, then discard this terminal scrollback:")
    print(f"heroku config:set GOOGLE_REFRESH_TOKEN='{refresh}'")


def _wait_for_code(host: str, port: int) -> str:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path != "/":
                self.send_response(404)
                self.end_headers()
                return
            if "code" in query:
                self.server.code = query["code"][0]  # type: ignore[attr-defined]
                body = b"Signed in. You can close this window."
                self.send_response(200)
            else:
                error = query.get("error", ["access_denied"])[0]
                self.server.error = error  # type: ignore[attr-defined]
                body = b"Login was not completed. You can close this window."
                self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            return

    try:
        server = HTTPServer((host, port), Handler)
    except OSError as exc:
        print(f"Could not listen on {host}:{port} ({exc.errno}).", file=sys.stderr)
        raise SystemExit(1) from None
    server.timeout = 1
    server.code = ""  # type: ignore[attr-defined]
    server.error = ""  # type: ignore[attr-defined]
    try:
        for _ in range(300):
            server.handle_request()
            if server.code or server.error:  # type: ignore[attr-defined]
                break
    finally:
        server.server_close()
    if server.error:  # type: ignore[attr-defined]
        print(f"Login failed ({server.error}).", file=sys.stderr)  # type: ignore[attr-defined]
        raise SystemExit(1)
    if not server.code:  # type: ignore[attr-defined]
        print("Login timed out waiting for the browser redirect.", file=sys.stderr)
        raise SystemExit(1)
    return str(server.code)  # type: ignore[attr-defined]


def _exchange(client_id: str, client_secret: str, redirect: str, code: str) -> dict:
    try:
        response = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect,
                "grant_type": "authorization_code",
            },
            timeout=30,
        )
    except httpx.HTTPError as exc:
        print(f"Login failed ({type(exc).__name__}).", file=sys.stderr)
        raise SystemExit(1) from None
    if response.status_code >= 400:
        print(f"Login failed ({_error_code(response)}).", file=sys.stderr)
        raise SystemExit(1)
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("refresh_token"), str):
        print(
            "Login failed (no_refresh_token). Revoke the app at myaccount.google.com and retry.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    access = payload.get("access_token")
    if not isinstance(access, str) or not access:
        print("Login failed (no_access_token).", file=sys.stderr)
        raise SystemExit(1)
    expires_in = payload.get("expires_in") or 3600
    try:
        ttl = int(expires_in)
    except (TypeError, ValueError):
        ttl = 3600
    import time

    return {
        "refresh_token": payload["refresh_token"],
        "access_token": access,
        "expires_at": time.time() + ttl,
    }


def _profile(access_token: str) -> str:
    try:
        response = httpx.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/profile",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
    except httpx.HTTPError as exc:
        print(f"Login failed ({type(exc).__name__}).", file=sys.stderr)
        raise SystemExit(1) from None
    if response.status_code >= 400:
        print(f"Login failed ({_error_code(response)}).", file=sys.stderr)
        raise SystemExit(1)
    payload = response.json()
    email = payload.get("emailAddress") if isinstance(payload, dict) else None
    if not isinstance(email, str) or "@" not in email:
        print("Login failed (profile).", file=sys.stderr)
        raise SystemExit(1)
    return email


def _error_code(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return str(response.status_code)
    if isinstance(payload, dict) and isinstance(payload.get("error"), str):
        return payload["error"]
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict) and isinstance(error.get("status"), str):
        return error["status"]
    return str(response.status_code)


if __name__ == "__main__":
    main()
