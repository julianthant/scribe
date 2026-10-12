import os

os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("WEBHOOK_SECRET", "test-webhook-secret-value")
os.environ.setdefault("GOOGLE_SHEET_ID", "sheetid0123456789")
os.environ.setdefault("MAILBOX_ADDRESS", "you@gmail.com")
os.environ.setdefault("GOOGLE_TOKEN_PATH", "/tmp/scribe-pytest/google_token.json")
os.environ.setdefault("STATE_DB_PATH", "/tmp/scribe-pytest/scribe.db")
os.environ.setdefault("WHISPER_MODEL_DIR", "/tmp/scribe-pytest/models")
os.environ.setdefault("LOCAL_WHISPER_ENABLED", "false")
