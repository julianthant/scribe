# Scribe

Scribe transcribes voicemail audio that lands in a free Gmail inbox and appends one row per message to a Google Sheet owned by that same account.

A Google Apps Script in that inbox runs every minute. It finds messages with `.mp3` or `.wav` attachments that are not labeled `scribe/processed`, and POSTs the Gmail message id to the FastAPI app on an Oracle Cloud Always Free VM. The POST is signed with HMAC-SHA256 and a shared secret. The app answers `202` immediately, then fetches the message with the Gmail API, transcribes the audio, appends the sheet, and applies the label.

A poll every 15 minutes on the VM catches anything the script missed. Dedup is the sheet's message-id column plus a small SQLite file. Groq's free `whisper-large-v3-turbo` model does the transcription. If Groq returns an error, the VM falls back to local `faster-whisper` (`small`, CPU, int8).

Nothing in this setup needs a Google Cloud billing account. Do not enable Pub/Sub, and do not link a billing account when the console offers one.

`MAILBOX_ADDRESS` is `scribe.smc@gmail.com`. That is the free Gmail inbox that receives forwarded voicemail. Sign in as that account for the Cloud project, the sheet, Apps Script, and `scribe-login`.

## What you need

- The Gmail account `scribe.smc@gmail.com`.
- A Google Cloud project with the Gmail API and Google Sheets API enabled, an OAuth desktop client, and the consent screen published to **Production**. No billing account.
- A blank Google Sheet in that Gmail account.
- A free Groq API key.
- An Oracle Cloud Always Free Ampere VM and a DNS name for `https://<domain>/gmail/notifications`.

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
7. Copy the client id and client secret into `.env` as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. Desktop clients allow the loopback redirect `http://127.0.0.1:8765/` without registering it. Do not commit the secret.

If Google will not show the consent screen after you publish, switch the audience back to **Testing**, add `scribe.smc@gmail.com` as a test user, and run `scribe-login` again every 7 days. Production is the setup that keeps the refresh token.

## 3. Create the sheet

While signed in as `scribe.smc@gmail.com`, create a blank sheet at [sheets.google.com](https://sheets.google.com). Leave the first tab named `Sheet1`, or set `GOOGLE_SHEET_TAB` to a single word with no spaces. Copy the spreadsheet id from the URL:

`https://docs.google.com/spreadsheets/d/<this-part>/edit`

That value is `GOOGLE_SHEET_ID`. Scribe writes the header row on the first append.

Columns:

`message_id`, `received_time`, `sender`, `subject`, `attachment_name`, `duration_seconds`, `transcript`, `model`, `processed_at`

## 4. Groq key

Create a key at [console.groq.com/keys](https://console.groq.com/keys). The free tier for `whisper-large-v3-turbo` is 20 requests per minute, 2,000 requests per day, 7,200 seconds of audio per hour, and 25 MB per request. Keep the key in `.env` only.

## 5. Configure the environment

```bash
cp .env.example .env
openssl rand -hex 32
```

Leave `MAILBOX_ADDRESS=scribe.smc@gmail.com`. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_SHEET_ID`, `GROQ_API_KEY`, and `WEBHOOK_SECRET` (the hex string, 16–128 characters). Set `SCRIBE_DOMAIN` to the hostname only, such as `scribe.example.com`. `GMAIL_LABEL` stays `scribe/processed`.

## 6. Create the Oracle VM

1. In the Oracle Cloud home region, create an Always Free Ampere instance: shape `VM.Standard.A1.Flex`, up to 2 OCPUs and 12 GB of memory, Ubuntu 22.04 or 24.04. If the console says **out of host capacity**, try another availability domain or try again later.
2. Add ingress rules for TCP 80 and TCP 443 on the subnet security list.
3. Oracle's Ubuntu image also filters those ports in iptables. On the VM:

```bash
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo apt-get update && sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save
```

4. Install Docker Engine and the Docker Compose plugin.
5. Create a DNS A record for `SCRIBE_DOMAIN` pointing at the VM's public IP.

An idle Always Free instance can be reclaimed if CPU, memory, and network stay under 20% for 7 days. A reclaim stops the VM. The Gmail inbox and the sheet stay, and the next poll writes any missing rows.

## 7. Sign in as the Gmail account

On a laptop that has this repo and a browser:

```bash
uv sync --extra dev
uv run scribe-login
```

Open the printed URL and sign in as `scribe.smc@gmail.com`. Google redirects the browser to `http://127.0.0.1:8765/`. The command checks the Gmail profile matches `MAILBOX_ADDRESS` and writes `data/google_token.json` with mode `600`. It does not print the tokens. On the unverified-app screen, choose **Advanced → Go to Scribe**.

Copy the token onto the VM volume:

```bash
docker compose run --rm --entrypoint "" -v "$PWD/data:/import:ro" scribe \
  sh -c "cp /import/google_token.json /data/google_token.json && chown app:app /data/google_token.json && chmod 600 /data/google_token.json"
```

To sign in on the VM instead, publish the login port and tunnel it:

```bash
# on the VM
docker compose run --rm -p 8765:8765 -e SCRIBE_OAUTH_HOST=0.0.0.0 scribe scribe-login

# on the laptop
ssh -L 8765:127.0.0.1:8765 <user>@<vm>
```

Open the URL on the laptop. The redirect hits the tunnel, then the container.

## 8. Start the service

```bash
docker compose build
docker compose up -d
curl https://scribe.example.com/health
```

`/health` returns `{"status":"ok","mailbox":"scribe.smc@gmail.com"}`.

`POST /gmail/notifications` checks `X-Scribe-Signature` against the raw body and returns `202` before any Gmail or transcription work. A bad signature is `401`. Logs include message ids, models, and durations. They do not include transcripts, refresh tokens, or the webhook secret.

After five failed attempts the message is labeled `scribe/processed` so the script stops pinging it, and the SQLite row stays `failed`. To retry, remove that label in Gmail and clear the row:

```bash
docker compose exec scribe python -c "import sqlite3; c=sqlite3.connect('/data/scribe.db'); c.execute(\"DELETE FROM messages WHERE status IN ('failed', 'pending')\"); c.commit()"
```

If a sheet row was already written, delete that row too or Scribe will treat the message as done.

## 9. Install the Apps Script

On the Scribe Gmail account, follow [apps-script/README.md](apps-script/README.md).

- Paste `apps-script/Code.gs` and `apps-script/appsscript.json` into a new project.
- Set script properties `WEBHOOK_URL=https://<domain>/gmail/notifications` and `WEBHOOK_SECRET` to the same secret as `.env`.
- Run `scribePoll` once and approve access (read Gmail, manage triggers, external request).
- Run `installTrigger` once. That creates a one-minute time trigger.

The script only sends message ids. The VM downloads the audio.

## 10. Forward voicemail into the inbox

On the mailbox that receives the voicemail (campus Gmail, another Gmail, or the phone system's mailbox):

1. **Settings → See all settings → Forwarding and POP/IMAP → Add a forwarding address**.
2. Enter the Scribe Gmail address (`scribe.smc@gmail.com`).
3. Gmail sends a confirmation message to that inbox. Open the Scribe inbox, open the confirmation, and click the link. If the page shows a code, enter it back on the source account. Forwarding does not start until this verification is accepted.
4. Create a filter on the source account: **Settings → Filters and Blocked Addresses → Create a new filter**. Criteria: has attachment, or the subject contains the voicemail wording your phone system uses. Action: **Forward it to** the Scribe Gmail. Leave a copy in the source inbox.
5. A campus Google Workspace tenant often blocks forwarding to an external address. If adding the address fails, ask the admin to allow forwarding to the Scribe Gmail.

Send a test `.mp3` or `.wav` to the Scribe inbox. Within about a minute the script posts the id, and one row appears in the sheet. The message gains the label `scribe/processed`. A second delivery of the same Gmail message must not add a second row.

## Optional GitHub Actions backup

`.github/workflows/reconcile.yml` runs the same poll on `workflow_dispatch` and hourly on UTC weekdays. The 15-minute poll on the VM is the one that matters while the VM is up. Add these repository secrets:

| Secret | Value |
| --- | --- |
| `GOOGLE_CLIENT_ID` | the desktop client id |
| `GOOGLE_CLIENT_SECRET` | the desktop client secret |
| `GOOGLE_SHEET_ID` | the sheet id |
| `GROQ_API_KEY` | the Groq key |
| `MAILBOX_ADDRESS` | `scribe.smc@gmail.com` |
| `GOOGLE_TOKEN_B64` | `base64 -w 0 data/google_token.json` |

The job deletes the token file at the end and does not upload it. If it warns that the file changed, update `GOOGLE_TOKEN_B64`. Actions cannot write secrets by itself. Prefer the VM's copy while the VM is healthy.

## systemd instead of Compose

Install ffmpeg, Caddy, and uv on the host. Create a `scribe` user, put the repo at `/opt/scribe`, and keep `.env` there. `uv sync --extra local` installs the app, including the local Whisper fallback. Run `scribe-login` as that user so `data/google_token.json` is mode `600`.

```bash
sudo cp deploy/scribe.service /etc/systemd/system/scribe.service
sudo systemctl enable --now scribe
```

Point a host Caddyfile at `127.0.0.1:8000` for the same domain. The unit listens on localhost only.

## Local development

```bash
uv sync --extra dev --extra local
cp .env.example .env
uv run scribe-login
uv run pytest
uv run ruff check
uv run ruff format
```

`uv run python -m app.poll` runs one reconciliation and exits, which is what Actions runs.

## Retries

A message with no audio attachment is labeled and marked skipped. A message whose audio bytes are not listed yet stays pending for a later poll and is not labeled. Groq errors fall back to local Whisper when `LOCAL_WHISPER_ENABLED=true` and the `local` extra is installed. Duration comes from ffprobe, then mutagen, then the wav header. Cells that start with `=`, `+`, `-`, or `@` are prefixed so the sheet stores them as text.
