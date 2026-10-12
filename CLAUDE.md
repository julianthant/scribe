# Scribe

FastAPI service that transcribes voicemail audio delivered to a free Gmail inbox and appends a row to a Google Sheet. It runs as one Heroku Basic web dyno.

An Apps Script in `apps-script/` runs every minute in that Gmail account and POSTs new message ids to `POST /gmail/notifications` with an HMAC signature. The app fetches the audio with the Gmail API, transcribes it, appends the sheet, and applies the `scribe/processed` label. APScheduler polls every 15 minutes inside the same web process.

The sheet `message_id` column is the durable dedup record. Attempt counts are in memory and reset on dyno restart. `GOOGLE_REFRESH_TOKEN` is a Heroku config var. Access tokens stay in memory. `LOCAL_WHISPER_ENABLED` defaults to false because a Basic dyno has 512 MB and the Heroku build does not install optional extras.

## Commands

```bash
uv sync --extra dev
uv run pytest
uv run ruff check
uv run ruff format
uv run scribe-login
uv run python -m app.poll
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Heroku runs `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT` from the `Procfile`.

## Layout

- `src/app/main.py` — app, `/health`, and lifespan
- `src/app/auth/` — installed-app OAuth login; the CLI prints the refresh token for `heroku config:set`
- `src/app/api/webhook.py` — HMAC check and fast 202
- `src/app/google/` — Gmail and Sheets calls as the signed-in user
- `src/app/pipeline/` — transcription, sheet rows, in-memory attempt counts, reconcile
- `src/app/services/runner.py` — worker queue and APScheduler poll
- `apps-script/` — one-minute Gmail notifier
- `Procfile`, `app.json`, `.python-version` — Heroku Basic web dyno

Configuration is environment variables. See `.env.example`. Do not log transcripts, refresh tokens, or the webhook secret. Do not enable Google Cloud billing. Do not add a second web dyno.
