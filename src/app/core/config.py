import re
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SHEET_ID = re.compile(r"[A-Za-z0-9_-]{10,}")


class Settings(BaseSettings):
    """Environment configuration. Field names match the environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    GOOGLE_CLIENT_ID: str = Field(min_length=1)
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REFRESH_TOKEN: str = ""
    MAILBOX_ADDRESS: str = ""
    WEBHOOK_SECRET: str = ""
    GOOGLE_SHEET_ID: str = ""
    GOOGLE_SHEET_TAB: str = "Sheet1"
    GMAIL_LABEL: str = "scribe/processed"
    SCRIBE_OAUTH_HOST: str = "127.0.0.1"
    SCRIBE_OAUTH_PORT: int = 8765
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "whisper-large-v3-turbo"
    LOCAL_WHISPER_ENABLED: bool = False
    WHISPER_MODEL: str = "small"
    WHISPER_MODEL_DIR: Path = Path("data/models")
    RECONCILE_INTERVAL_SECONDS: int = 900
    RECONCILE_LOOKBACK_HOURS: int = 48
    MAX_ATTEMPTS: int = 5
    RETRY_BACKOFF_SECONDS: float = 2
    LOG_LEVEL: str = "INFO"

    @field_validator("MAILBOX_ADDRESS")
    @classmethod
    def mailbox(cls, value: str) -> str:
        cleaned = value.strip()
        if cleaned and "@" not in cleaned:
            raise ValueError("MAILBOX_ADDRESS must be the Gmail address that receives voicemail")
        return cleaned

    @field_validator("GOOGLE_SHEET_ID")
    @classmethod
    def sheet_id(cls, value: str) -> str:
        cleaned = value.strip()
        if cleaned and _SHEET_ID.fullmatch(cleaned) is None:
            raise ValueError("GOOGLE_SHEET_ID must be the id from the sheet URL")
        return cleaned

    @field_validator("GOOGLE_REFRESH_TOKEN")
    @classmethod
    def refresh_token(cls, value: str) -> str:
        return value.strip()

    @field_validator("GOOGLE_SHEET_TAB", "GMAIL_LABEL")
    @classmethod
    def plain_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or any(char in cleaned for char in "\r\n\"'! "):
            raise ValueError("name must be a single token without quotes")
        return cleaned

    @field_validator("SCRIBE_OAUTH_HOST")
    @classmethod
    def oauth_host(cls, value: str) -> str:
        if value not in {"127.0.0.1", "0.0.0.0"}:
            raise ValueError("SCRIBE_OAUTH_HOST must be 127.0.0.1 or 0.0.0.0")
        return value

    @field_validator("RECONCILE_INTERVAL_SECONDS")
    @classmethod
    def positive_interval(cls, value: int) -> int:
        if value < 60:
            raise ValueError("interval must be at least 60 seconds")
        return value

    @field_validator("MAX_ATTEMPTS")
    @classmethod
    def attempts(cls, value: int) -> int:
        if value < 1:
            raise ValueError("MAX_ATTEMPTS must be at least 1")
        return value


class ConfigError(SystemExit):
    """Raised as SystemExit so CLI and startup print a message and stop."""


def load_settings() -> Settings:
    try:
        return Settings()
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            lines = ["Configuration error:"]
            for error in exc.errors():
                field = ".".join(str(part) for part in error["loc"])
                lines.append(f"  {field}: {error['msg']}")
            raise ConfigError("\n".join(lines)) from None
        raise


def _runtime_problems(settings: Settings) -> list[str]:
    missing: list[str] = []
    if not settings.GROQ_API_KEY:
        missing.append("GROQ_API_KEY is required")
    if not settings.GOOGLE_CLIENT_SECRET:
        missing.append("GOOGLE_CLIENT_SECRET is required")
    if not settings.GOOGLE_REFRESH_TOKEN:
        missing.append("GOOGLE_REFRESH_TOKEN is required")
    if not settings.MAILBOX_ADDRESS:
        missing.append("MAILBOX_ADDRESS is required")
    if not settings.GOOGLE_SHEET_ID:
        missing.append("GOOGLE_SHEET_ID is required")
    return missing


def require_runtime(settings: Settings) -> None:
    missing = _runtime_problems(settings)
    if missing:
        raise ConfigError("Configuration error:\n  " + "\n  ".join(missing))


def require_server(settings: Settings) -> None:
    missing = _runtime_problems(settings)
    if not 16 <= len(settings.WEBHOOK_SECRET) <= 128:
        missing.append("WEBHOOK_SECRET must be 16 to 128 characters")
    if missing:
        raise ConfigError("Configuration error:\n  " + "\n  ".join(missing))
