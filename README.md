# Scribe

Scribe transcribes voicemail audio that lands in a free Gmail inbox and appends one row per message to a Google Sheet owned by that same account.

A Google Apps Script in that inbox runs every minute. It finds messages with `.mp3` or `.wav` attachments that are not labeled `scribe/processed`, and POSTs the Gmail message id to the FastAPI app on a Heroku Basic web dyno. The POST is signed with HMAC-SHA256 and a shared secret. The app answers `202` immediately, then fetches the message with the Gmail API, transcribes the audio, appends the sheet, and applies the label.

The web process also polls Gmail every 15 minutes, in process, with APScheduler. That poll is the backup when the script misses a message. The Google Sheet `message_id` column is the durable dedup record. Attempt counts live only in the dyno's memory and reset on restart. Groq's free `whisper-large-v3-turbo` model does the transcription. Local `faster-whisper` stays off: a Basic dyno has 512 MB, and the Heroku build does not install the `local` extra.

Nothing in this setup needs a Google Cloud billing account. Do not enable Pub/Sub, and do not link a billing account when the console offers one.

`MAILBOX_ADDRESS` is `scribe.smc@gmail.com`. That is the free Gmail inbox that receives forwarded voicemail. Sign in as that account for the Cloud project, the sheet, Apps Script, and `scribe-login`.

## What you need

- The Gmail account `scribe.smc@gmail.com`.
- A Google Cloud project with the Gmail API and Google Sheets API enabled, an OAuth desktop client, and the consent screen published to **Production**. No billing account.
- A blank Google Sheet in that Gmail account.
- A free Groq API key.
- A Heroku account with GitHub Student Pack credit, the Heroku CLI, and one Basic web dyno. Eco dynos sleep, so a webhook POST would fail while the dyno is asleep. Basic does not sleep. It bills about $0.01 per hour, capped near $7 per month. Student Pack credit covers that while the credit lasts.

## 1. Create the Gmail inbox

Use `scribe.smc@gmail.com`. Sign in to this account for the Cloud project, the sheet, Apps Script, and `scribe-login`. The Gmail API calls `/users/me`, so the signed-in account is the mailbox Scribe reads. Leave `MAILBOX_ADDRESS=scribe.smc@gmail.com`.

## 2. Google Cloud project, without billing

1. Open [Google Cloud Console](https://console.cloud.google.com/) while signed in as `scribe.smc@gmail.com`.
2. Create a project named `Scribe`. If a banner asks you to link a billing account, dismiss it. This project must stay on the free tier.
3. **APIs & Services → Library**. Enable **Gmail API** and **Google Sheets API**. Do not enable Cloud Pub/Sub.
4. **APIs & Services → OAuth consent screen**.
   - User type: **External**.
   - App name: `Scribe`. User support email and developer contact: `scribe.smc@gmail.com`.
   - Scopes: add `https://www.googleapis.com/auth/gmail.modify` and `https://www.googleapis.com/auth/spreadsheets`.
   - Save, then click **Publish app** so the status is **In production**.
5. `gmail.modify` is a restricted scope, so Google shows an unverified-app warning. That warning is expected. On the consent screen choose **Advanced**, then **Go to Scribe**. An unverified production app can be granted by about 100 users, which covers this one mailbox, and the refresh token is not the 7-day Testing token. Do not submit the app for Google's restricted-scope verification. That review is for a public app and is not part of this free setup.
6. **APIs & Services → Credentials → Create credentials → OAuth client ID**. Application type: **Desktop app**. Name it `Scribe login`.
7. Copy the client id and client secret. Desktop clients allow the loopback redirect `http://127.0.0.1:8765/` without registering it. Do not commit the secret.

If Google will not show the consent screen after you publish, switch the audience back to **Testing**, add `scribe.smc@gmail.com` as a test user, and run `scribe-login` again every 7 days. Production is the setup that keeps the refresh token.

## 3. Create the sheet

While signed in as `scribe.smc@gmail.com`, create a blank sheet at [sheets.google.com](https://sheets.google.com). Leave the first tab named `Sheet1`, or set `GOOGLE_SHEET_TAB` to a single word with no spaces. Copy the spreadsheet id from the URL:

`https://docs.google.com/spreadsheets/d/<this-part>/edit`

That value is `GOOGLE_SHEET_ID`. Scribe writes the header row on the first append. Column A, `message_id`, is how a restarted dyno knows a message was already written.

Columns:

`message_id`, `received_time`, `sender`, `subject`, `attachment_name`, `duration_seconds`, `transcript`, `model`, `processed_at`

## 4. Groq key

Create a key at [console.groq.com/keys](https://console.groq.com/keys). The free tier for `whisper-large-v3-turbo` is 20 requests per minute, 2,000 requests per day, 7,200 seconds of audio per hour, and 25 MB per request.

## 5. Create the Heroku app

Install the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli) and log in:

```bash
heroku login
heroku create <app> --stack heroku-24
heroku ps:resize web=basic
heroku ps:scale web=1
```

`<app>` becomes the hostname `https://<app>.herokuapp.com`. Keep a single web dyno. Two web dynos can both append a row for the same message, because the sheet append is not locked across processes.

Connect the GitHub repo and deploy this branch (or `main` after it merges):

1. Heroku Dashboard → the app → **Deploy** → **Deployment method** → **GitHub**.
2. Connect `julianthant/scribe`.
3. Deploy the branch. Automatic deploys from `main` are fine after the pull request merges.

The repo has a `Procfile`, `app.json`, `pyproject.toml`, `uv.lock`, and `.python-version` (`3.12`). Heroku's Python buildpack runs `uv sync --locked --no-default-groups`, so the `dev` and `local` extras are not installed. The web process is:

```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

The dyno filesystem is wiped on restart and on every deploy. Do not put the refresh token or a database file on disk.

A Basic dyno costs about $0.01 per hour, up to about $7 in a month. GitHub Student Pack credit pays that until the credit runs out. Do not switch the formation to Eco.

## 6. Sign in on a laptop and set config vars

On a laptop that has this repo and a browser, fill `.env` with the client id, client secret, and `MAILBOX_ADDRESS=scribe.smc@gmail.com`. The refresh token is not in `.env` yet.

```bash
uv sync --extra dev
uv run scribe-login
```

Open the printed URL and sign in as `scribe.smc@gmail.com`. Google redirects the browser to `http://127.0.0.1:8765/`. On the unverified-app screen, choose **Advanced → Go to Scribe**. The command checks the Gmail profile matches `MAILBOX_ADDRESS`. It then prints one shell command. It does not write a token file. Copy that command, run it, and clear the terminal scrollback. Do not commit the value.

```bash
heroku config:set --app <app> \
  MAILBOX_ADDRESS=scribe.smc@gmail.com \
  GOOGLE_CLIENT_ID='<client id>' \
  GOOGLE_CLIENT_SECRET='<client secret>' \
  GOOGLE_REFRESH_TOKEN='<value printed by scribe-login>' \
  GOOGLE_SHEET_ID='<sheet id>' \
  GOOGLE_SHEET_TAB=Sheet1 \
  GMAIL_LABEL=scribe/processed \
  GROQ_API_KEY='<groq key>' \
  GROQ_MODEL=whisper-large-v3-turbo \
  WEBHOOK_SECRET="$(openssl rand -hex 32)" \
  LOCAL_WHISPER_ENABLED=false \
  LOG_LEVEL=INFO
```

Access tokens are cached in the web process only. If Google later replaces the refresh token, the log says a replacement credential is in memory and the dyno must be restarted after you update `GOOGLE_REFRESH_TOKEN`. The log does not contain the credential. Run `scribe-login` again to obtain the new value.

`heroku config:get WEBHOOK_SECRET --app <app>` is the value Apps Script must use. If you created the app from `app.json` and Heroku generated `WEBHOOK_SECRET`, use that generated value instead of setting a new one.

## 7. Deploy and check health

Deploy from the Heroku GitHub tab, or from a checkout that already has `heroku git:remote --app <app>`:

```bash
git push heroku <branch>:main
curl https://<app>.herokuapp.com/health
```

`/health` returns `{"status":"ok","mailbox":"scribe.smc@gmail.com"}`.

`POST /gmail/notifications` checks `X-Scribe-Signature` against the raw body and returns `202` before any Gmail or transcription work. A bad signature is `401`. Logs include message ids, models, and durations. They do not include transcripts, refresh tokens, or the webhook secret.

The process binds `$PORT` before the first poll. APScheduler runs that poll about 15 seconds after boot, then every `RECONCILE_INTERVAL_SECONDS` (900). One web dyno, so the poll does not add a second process.

After five failed attempts the message is labeled `scribe/processed` so the script stops posting it. Those attempt counts reset when the dyno restarts. To transcribe again, remove the label `scribe/processed` in Gmail. If a sheet row was already written, delete that row too. There is no database file to edit.

## 8. Install the Apps Script

On the Scribe Gmail account, follow [apps-script/README.md](apps-script/README.md).

- Paste `apps-script/Code.gs` and `apps-script/appsscript.json` into a new project.
- Set script properties `WEBHOOK_URL=https://<app>.herokuapp.com/gmail/notifications` and `WEBHOOK_SECRET` to the same secret as `heroku config:get WEBHOOK_SECRET`.
- Run `scribePoll` once and approve access (read Gmail, manage triggers, external request).
- Run `installTrigger` once. That creates a one-minute time trigger.

The script only sends message ids. The dyno downloads the audio.

## 9. Forward voicemail into the inbox

On the mailbox that receives the voicemail (campus Gmail, another Gmail, or the phone system's mailbox):

1. **Settings → See all settings → Forwarding and POP/IMAP → Add a forwarding address**.
2. Enter the Scribe Gmail address (`scribe.smc@gmail.com`).
3. Gmail sends a confirmation message to that inbox. Open the Scribe inbox, open the confirmation, and click the link. If the page shows a code, enter it back on the source account. Forwarding does not start until this verification is accepted.
4. Create a filter on the source account: **Settings → Filters and Blocked Addresses → Create a new filter**. Criteria: has attachment, or the subject contains the voicemail wording your phone system uses. Action: **Forward it to** the Scribe Gmail. Leave a copy in the source inbox.
5. A campus Google Workspace tenant often blocks forwarding to an external address. If adding the address fails, ask the admin to allow forwarding to the Scribe Gmail.

Send a test `.mp3` or `.wav` to the Scribe inbox. Within about a minute the script posts the id, and one row appears in the sheet. The message gains the label `scribe/processed`. A second delivery of the same Gmail message must not add a second row.

## Polling cost

The 15-minute poll runs inside the Basic web dyno. It does not add a charge on top of that dyno.

Heroku Scheduler is a $0 add-on, but each job runs as a one-off dyno billed at the same rate (about $0.01 per hour, prorated to the job's runtime). `heroku run python -m app.poll` bills the same way. Do not add Heroku Scheduler while the web dyno is up.

## Optional GitHub Actions poll

`.github/workflows/reconcile.yml` is manual (`workflow_dispatch` only). Leave it unused while the dyno is running. Two writers can both append before either sees the new sheet row. If you use it while the dyno is down, add these repository secrets:

| Secret | Value |
| --- | --- |
| `GOOGLE_CLIENT_ID` | the desktop client id |
| `GOOGLE_CLIENT_SECRET` | the desktop client secret |
| `GOOGLE_REFRESH_TOKEN` | the same value as the Heroku config var |
| `GOOGLE_SHEET_ID` | the sheet id |
| `GROQ_API_KEY` | the Groq key |
| `MAILBOX_ADDRESS` | `scribe.smc@gmail.com` |

If Google replaces the refresh token during that job, update the Heroku config var and this secret from a new `scribe-login`. The job cannot write the secret back.

## Local development

```bash
uv sync --extra dev
cp .env.example .env
uv run scribe-login
uv run pytest
uv run ruff check
uv run ruff format
```

`LOCAL_WHISPER_ENABLED` defaults to false. To try the local model on a laptop, `uv sync --extra dev --extra local` and set `LOCAL_WHISPER_ENABLED=true`. That extra is not part of the Heroku slug.

`uv run python -m app.poll` runs one reconciliation and exits. On Heroku that command is a billed one-off dyno. The in-process timer is the path that stays inside the web dyno.

## Retries

A message with no audio attachment is labeled and marked skipped. A message whose audio bytes are not listed yet stays pending for a later poll and is not labeled. Groq errors raise until `MAX_ATTEMPTS`, then the message is labeled so Apps Script stops. Local Whisper runs only when `LOCAL_WHISPER_ENABLED=true` and the `local` extra is installed. Duration comes from ffprobe when it is on `PATH`, then mutagen, then the wav header. Heroku does not include ffmpeg, so clips larger than 24 MB are not split there; voicemail clips are smaller than that. Cells that start with `=`, `+`, `-`, or `@` are prefixed so the sheet stores them as text.
