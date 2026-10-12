# Scribe

FastAPI service that transcribes voicemail audio delivered to a free Gmail inbox and appends a row to a Google Sheet.

An Apps Script in `apps-script/` runs every minute in that Gmail account and POSTs new message ids to `POST /gmail/notifications` with an HMAC signature. The app fetches the audio with the Gmail API, transcribes it, appends the sheet, and applies the `scribe/processed` label. A poll every 15 minutes catches anything the script missed.

## Commands

```bash
uv sync --extra dev --extra local
uv run pytest
uv run ruff check
uv run ruff format
uv run scribe-login
uv run python -m app.poll
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Layout

- `src/app/main.py` — app, `/health`, and lifespan
- `src/app/auth/` — installed-app OAuth login and the mode-600 token file
- `src/app/api/webhook.py` — HMAC check and fast 202
- `src/app/google/` — Gmail and Sheets calls as the signed-in user
- `src/app/pipeline/` — transcription, sheet rows, SQLite dedup, reconcile
- `apps-script/` — one-minute Gmail notifier
- `deploy/` — Compose entrypoint, Caddyfile, systemd unit

Configuration is environment variables. See `.env.example`. Do not log transcripts, refresh tokens, or the webhook secret. Do not enable Google Cloud billing.
