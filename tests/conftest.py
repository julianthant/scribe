import os

os.environ.setdefault("MS_CLIENT_ID", "00000000-0000-0000-0000-000000000000")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("GRAPH_CLIENT_STATE", "test-client-state-value")
os.environ.setdefault("GRAPH_WEBHOOK_URL", "https://scribe.example.com/graph/notifications")
os.environ.setdefault("MAILBOX_ADDRESS", "smc.scribe@outlook.com")
os.environ.setdefault("TOKEN_CACHE_PATH", "/tmp/scribe-pytest/token_cache.json")
os.environ.setdefault("STATE_DB_PATH", "/tmp/scribe-pytest/scribe.db")
os.environ.setdefault("WHISPER_MODEL_DIR", "/tmp/scribe-pytest/models")
os.environ.setdefault("LOCAL_WHISPER_ENABLED", "false")
