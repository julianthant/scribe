# Contributing

Scribe is a small FastAPI service. Issues and pull requests are welcome.

```bash
uv sync --extra dev --extra local
uv run ruff check
uv run ruff format
uv run pytest
```

Do not commit `.env`, refresh tokens, or transcription logs. Tests mock Gmail, Sheets, and Groq.
