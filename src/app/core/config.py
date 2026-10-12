from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment configuration. Field names match the environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    MS_CLIENT_ID: str = Field(min_length=1)
    MS_AUTHORITY: str = "https://login.microsoftonline.com/consumers"
    MAILBOX_ADDRESS: str = "smc.scribe@outlook.com"
    GRAPH_WEBHOOK_URL: str = ""
    GRAPH_CLIENT_STATE: str = ""
    TOKEN_CACHE_PATH: Path = Path("data/token_cache.json")
    STATE_DB_PATH: Path = Path("data/scribe.db")
    ONEDRIVE_XLSX_PATH: str = "Scribe/voicemails.xlsx"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "whisper-large-v3-turbo"
    LOCAL_WHISPER_ENABLED: bool = True
    WHISPER_MODEL: str = "small"
    WHISPER_MODEL_DIR: Path = Path("data/models")
    RECONCILE_INTERVAL_SECONDS: int = 900
    RECONCILE_LOOKBACK_HOURS: int = 48
    SUBSCRIPTION_RENEW_INTERVAL_SECONDS: int = 86400
    SUBSCRIPTION_LIFETIME_DAYS: int = 6
    MAX_ATTEMPTS: int = 5
    RETRY_BACKOFF_SECONDS: float = 2
    LOG_LEVEL: str = "INFO"

    @field_validator("MS_AUTHORITY")
    @classmethod
    def authority_is_consumers(cls, value: str) -> str:
        if not value.startswith("https://login.microsoftonline.com/"):
            raise ValueError("MS_AUTHORITY must be a login.microsoftonline.com URL")
        return value.rstrip("/")

    @field_validator("ONEDRIVE_XLSX_PATH")
    @classmethod
    def workbook_path(cls, value: str) -> str:
        cleaned = value.strip().lstrip("/")
        if not cleaned.lower().endswith(".xlsx"):
            raise ValueError("ONEDRIVE_XLSX_PATH must end with .xlsx")
        if ".." in cleaned.split("/"):
            raise ValueError("ONEDRIVE_XLSX_PATH must not contain '..'")
        return cleaned

    @field_validator("RECONCILE_INTERVAL_SECONDS", "SUBSCRIPTION_RENEW_INTERVAL_SECONDS")
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
    if not settings.GROQ_API_KEY:
        return ["GROQ_API_KEY is required"]
    return []


def require_runtime(settings: Settings) -> None:
    missing = _runtime_problems(settings)
    if missing:
        raise ConfigError("Configuration error:\n  " + "\n  ".join(missing))


def require_server(settings: Settings) -> None:
    missing = _runtime_problems(settings)
    if not settings.GRAPH_WEBHOOK_URL.startswith("https://"):
        missing.append("GRAPH_WEBHOOK_URL must be an https URL that Microsoft Graph can reach")
    if not settings.GRAPH_WEBHOOK_URL.rstrip("/").endswith("/graph/notifications"):
        missing.append("GRAPH_WEBHOOK_URL must end with /graph/notifications")
    if not 16 <= len(settings.GRAPH_CLIENT_STATE) <= 128:
        missing.append("GRAPH_CLIENT_STATE must be 16 to 128 characters")
    if missing:
        raise ConfigError("Configuration error:\n  " + "\n  ".join(missing))
