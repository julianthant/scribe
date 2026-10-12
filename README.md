# Scribe

Scribe watches the personal Outlook.com mailbox `smc.scribe@outlook.com`. When a message with an `.mp3` or `.wav` attachment arrives, it transcribes the audio and appends one row to an Excel workbook on that account's OneDrive.

The service runs on an always-on free VM so Microsoft Graph can deliver webhooks. A poll every 15 minutes catches anything the webhook missed. An optional GitHub Actions job can run the same poll when the VM is down.

Transcription uses Groq's free `whisper-large-v3-turbo` model. If Groq returns an error or a rate limit, the VM falls back to local `faster-whisper` (`small`, CPU, int8). Files over 24 MB are re-encoded with ffmpeg and split before upload.

## What you need

- A free Outlook.com account. This project uses `smc.scribe@outlook.com`.
- An Entra app registration for personal Microsoft accounts, with no client secret.
- A free Groq API key.
- An Oracle Cloud Always Free Ampere VM (or the GitHub Actions poll alone, if no VM capacity is available).
- A DNS name pointing at that VM, so Graph can reach `https://<domain>/graph/notifications`.

Graph must get an HTTP response in about 3 seconds, and it validates the webhook URL in about 10 seconds. Hosts that sleep when idle (Render, and Koyeb after an hour) miss that window. Fly.io's trial is not an ongoing free tier. Oracle's Always Free Ampere VM stays up. The 15-minute poll and the optional Actions job still record mail if a notification is dropped.

## 1. Register the Entra app

1. Open [App registrations](https://entra.microsoft.com/) and choose **New registration**.
2. Name it `Scribe`.
3. Supported account types: **Personal Microsoft accounts only**.
4. Redirect URI: **Public client/native (mobile & desktop)** and `https://login.microsoftonline.com/common/oauth2/nativeclient`.
5. Register, then copy the **Application (client) ID**.
6. Open **Authentication** and set **Allow public client flows** to **Yes**.
7. Open **API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated** and add `Mail.Read` and `Files.ReadWrite`.
8. Do not create a client secret. Consent happens when you sign in.

`Mail.Read` cannot move or delete mail. Processed messages stay in the inbox. The workbook is the record of what was transcribed.

## 2. Create a Groq key

Create a key at [console.groq.com/keys](https://console.groq.com/keys). The free tier for `whisper-large-v3-turbo` is 20 requests per minute, 2,000 requests per day, 7,200 seconds of audio per hour, and 25 MB per request. Keep the key in `.env` only.

## 3. Configure the environment

```bash
cp .env.example .env
```

Set these values:

| Variable | Value |
| --- | --- |
| `MAILBOX_ADDRESS` | `smc.scribe@outlook.com` |
| `MS_CLIENT_ID` | the Entra application id |
| `GROQ_API_KEY` | the Groq key |
| `GRAPH_CLIENT_STATE` | a random string, 16 to 128 characters |
| `GRAPH_WEBHOOK_URL` | `https://<your-domain>/graph/notifications` |
| `ONEDRIVE_XLSX_PATH` | `Scribe/voicemails.xlsx` |
| `SCRIBE_DOMAIN` | the hostname only, such as `scribe.example.com` |

`SCRIBE_DOMAIN` is for Caddy. The Python app does not read it.

Generate a client state with:

```bash
openssl rand -hex 32
```

## 4. Create the Oracle VM

1. In the Oracle Cloud home region, create an Always Free Ampere instance: shape `VM.Standard.A1.Flex`, up to 2 OCPUs and 12 GB of memory, Ubuntu 22.04 or 24.04. If the console says **out of host capacity**, try another availability domain or try again later.
2. Add ingress rules for TCP 80 and TCP 443 on the subnet security list.
3. Oracle's Ubuntu image also filters those ports in iptables. On the VM, allow them and save the rules:

```bash
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo apt-get update && sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save
```

4. Install Docker Engine and the Docker Compose plugin.
5. Create a DNS A record for `SCRIBE_DOMAIN` pointing at the VM's public IP.

An idle Always Free instance can be reclaimed if CPU, memory, and network stay under 20% for 7 days. A reclaim stops the VM; it does not delete the mailbox. The inbox still holds the audio, and the next poll writes any missing rows.

If you cannot get Ampere capacity, skip the VM and use the [Actions poll](#8-optional-github-actions-backup) as the scheduler. Webhooks need the VM.

## 5. Sign in as the mailbox

On the VM:

```bash
git clone <this-repo> scribe && cd scribe
cp .env.example .env
# edit .env with the values from step 3
docker compose build
docker compose run --rm -it scribe scribe-login
```

`scribe-login` prints a device-code URL. Open it and sign in as **`smc.scribe@outlook.com`**. Graph calls `/me`, so the signed-in account is the mailbox Scribe reads. The cache is stored at `/data/token_cache.json` on the Compose volume, mode `600`. The command does not print tokens.

## 6. Start the service

```bash
docker compose up -d
curl https://scribe.example.com/health
```

`/health` returns `{"status":"ok","mailbox":"smc.scribe@outlook.com"}`.

On startup the app creates a Graph subscription on `me/mailFolders('Inbox')/messages` and renews it daily (the lifetime is 6 days; Graph's maximum is under 7). Graph checks the webhook URL during creation, so DNS and Caddy must already be working. If they are not, the app retries every 5 minutes. A notification is answered with `202` before transcription starts. `validationToken` is echoed as `text/plain` with no other work.

Rows go to `Scribe/voicemails.xlsx` on the OneDrive of `smc.scribe@outlook.com`. Columns:

`message_id`, `received_time`, `sender`, `subject`, `attachment_name`, `duration_seconds`, `transcript`, `model`, `processed_at`

The same message id is written once. The workbook and a small SQLite file (`/data/scribe.db`) are both checked. A crash mid-transcription leaves the row pending and the next attempt retries it. After 5 failed attempts the row stays `failed` until you clear it. A message that still has no attachment list after 5 tries also stops; delete that row the same way.

```bash
docker compose exec scribe python -c "import sqlite3; c=sqlite3.connect('/data/scribe.db'); c.execute(\"DELETE FROM messages WHERE status IN ('failed', 'pending')\"); c.commit()"
```

Logs include message ids, models, and durations. They do not include transcripts, access tokens, or refresh tokens.

## 7. Forward voicemail into the mailbox

On the mailbox that receives the voicemail (often a campus account), create an Outlook on the web rule:

- Condition: the message has an attachment, or the subject contains the voicemail wording your phone system uses.
- Action: **Redirect** to `smc.scribe@outlook.com`.

Use redirect rather than forward. Redirect keeps the original sender and the audio attachment. A campus Microsoft 365 tenant often blocks redirect to an external address. If the rule saves but mail never arrives, the tenant blocked it. Ask campus IT to allow redirect to `smc.scribe@outlook.com`.

Send a test `.mp3` or `.wav` to `smc.scribe@outlook.com`. One new row should appear. Delivering the same message again must not add a second row.

## 8. Optional GitHub Actions backup

The workflow `.github/workflows/reconcile.yml` runs the same poll on `workflow_dispatch` and hourly on UTC weekdays. Add these repository secrets:

| Secret | Value |
| --- | --- |
| `MS_CLIENT_ID` | the Entra application id |
| `GROQ_API_KEY` | the Groq key |
| `TOKEN_CACHE_B64` | `base64 -w 0 /data/token_cache.json` from the VM |

Actions deduplicates with the workbook, because its SQLite file is discarded after each job. Local Whisper is disabled there. The job deletes the cache file at the end and does not upload it as an artifact.

Microsoft rotates refresh tokens. If the job warns that the cache changed, update `TOKEN_CACHE_B64`. Actions cannot write secrets by itself. Running the VM and this schedule together can invalidate each other's refresh token. Prefer the VM while it is healthy, and use **Run workflow** when the VM is down. If sign-in breaks, run `scribe-login` again and replace the secret.

## 9. systemd instead of Compose

Install ffmpeg, Caddy, and uv on the host. Create a `scribe` user, put the repo at `/opt/scribe`, and keep `.env` there. `uv sync --extra local` installs the app, including the local Whisper fallback. Run `scribe-login` as that user so `data/token_cache.json` is mode `600`.

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

`scribe-login` needs `MS_CLIENT_ID`. The server also needs `GROQ_API_KEY`, `GRAPH_WEBHOOK_URL`, and `GRAPH_CLIENT_STATE`. `uv run python -m app.poll` runs one reconciliation and exits, which is what Actions runs.

## Workbook and retries

A message with no audio attachment is marked skipped and is not transcribed again. A message that claims attachments but lists none yet stays pending for a later poll. Groq errors fall back to local Whisper when `LOCAL_WHISPER_ENABLED=true` and the `local` extra is installed. Duration comes from ffprobe, then mutagen, then the wav header.
