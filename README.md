# Scribe

A FastAPI service that reads an Outlook mailbox through the Microsoft Graph API. It is the API prototype for Scribe, a voicemail tracker I built for the Insurance Claims office at Santa Monica College. In that system, voicemails arrive as Outlook emails, get transcribed with Azure AI Speech-to-Text and go into a shared tracker.

## Status

Early prototype, paused in September 2025. It does not run yet. The inbox endpoints are written, but three things block them:

- `src/app/api/v1/__init__.py` still imports the boilerplate routers that were deleted, and it does not register the inbox router.
- `get_ms_token` in `src/app/api/dependencies.py` calls `.json()` on the request before awaiting it.
- `src/app/crud/crud_inbox.py` is empty.

## Where the code comes from

This repo started as a clone of [benavlabs/FastAPI-boilerplate](https://github.com/benavlabs/FastAPI-boilerplate), which is why the history includes commits from that project's contributors. My changes are in the last two commits:

- Removed the boilerplate's users, posts, tiers, rate limiting, caching, background worker and migrations.
- Added Microsoft Graph sign-in with the OAuth 2.0 client-credentials flow (`src/app/api/dependencies.py`).
- Added the inbox endpoints (`src/app/api/v1/inbox.py`) and the email and attachment schemas.
- Renamed the project and moved the Docker image to Python 3.12.

## Planned endpoints

These are defined in `src/app/api/v1/inbox.py`.

| Method and path | Returns |
| --- | --- |
| `GET /api/v1/inbox/{user_id}` | All messages in the user's mailbox |
| `GET /api/v1/inbox/{user_id}/messages/{message_id}` | One message |
| `GET /api/v1/inbox/{user_id}/messages/{message_id}/attachments` | The message's attachments |
| `GET /api/v1/inbox/{user_id}/messages/{message_id}/attachments/{attachment_id}` | One attachment |

## Configuration

Register an app in Microsoft Entra ID with the `Mail.Read` application permission, then set:

```bash
MS_TENANT_ID=
MS_CLIENT_ID=
MS_CLIENT_SECRET=
```

## License

MIT, inherited from FastAPI-boilerplate. See `LICENSE.md`.
