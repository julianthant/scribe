# Scribe

FastAPI service that transcribes voicemail audio delivered to the personal Outlook.com mailbox `smc.scribe@outlook.com` and appends a row to an OneDrive workbook.

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
- `src/app/auth/` — MSAL device-code login and the mode-600 token cache
- `src/app/api/webhook.py` — Graph validation and notification ack
- `src/app/graph/client.py` — delegated Graph calls as `/me`
- `src/app/pipeline/` — transcription, workbook, SQLite dedup, reconcile, subscription renewal
- `deploy/` — Compose entrypoint, Caddyfile, systemd unit

Configuration is environment variables. See `.env.example`. Personal Outlook.com uses the `consumers` authority and delegated `Mail.Read` plus `Files.ReadWrite`. Do not log transcripts or tokens.
