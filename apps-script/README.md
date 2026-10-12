# Apps Script notifier

This script runs inside the Gmail account that receives forwarded voicemail. Every minute it searches for `.mp3` and `.wav` messages that do not have the `scribe/processed` label, and POSTs each Gmail message id to the Heroku app.

The app fetches the audio with the Gmail API, transcribes it, appends a Google Sheet row, and applies the label. Until that label exists, the script will ping the same id again. The sheet `message_id` column is the durable dedup record.

## Install

1. Sign in to the Scribe Gmail account.
2. Open [script.google.com](https://script.google.com) → **New project**. Name it `Scribe`.
3. Replace `Code.gs` with the contents of `Code.gs` in this folder. In **Project Settings**, check **Show "appsscript.json" manifest file**, then replace that file with `appsscript.json`.
4. **Project Settings → Script properties**:

| Property | Value |
| --- | --- |
| `WEBHOOK_URL` | `https://<app>.herokuapp.com/gmail/notifications` |
| `WEBHOOK_SECRET` | the same value as `heroku config:get WEBHOOK_SECRET` |

5. Select `scribePoll` and **Run** once. Approve the consent screen (read Gmail, manage triggers, call an external URL).
6. Select `installTrigger` and **Run** once. That creates a time-driven trigger every minute. You can also add it from the **Triggers** clock: function `scribePoll`, time-driven, minutes timer, every minute.

Do not link a billing account to the Apps Script project. GmailApp and UrlFetchApp do not need one.

The script does not log the secret or message bodies. A non-202 response is logged with the status code and message id.
