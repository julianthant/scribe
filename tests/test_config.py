import pytest
from pydantic import ValidationError
from tests.helpers import settings_for

from app.core.config import ConfigError, Settings, load_settings, require_server


def test_default_mailbox_is_the_scribe_outlook_account(monkeypatch, tmp_path):
    monkeypatch.delenv("MAILBOX_ADDRESS", raising=False)
    settings = Settings(
        MS_CLIENT_ID="client",
        TOKEN_CACHE_PATH=tmp_path / "token.json",
        STATE_DB_PATH=tmp_path / "scribe.db",
    )
    assert settings.MAILBOX_ADDRESS == "smc.scribe@outlook.com"


def test_require_server_names_each_problem(tmp_path):
    settings = settings_for(
        tmp_path,
        GROQ_API_KEY="",
        GRAPH_WEBHOOK_URL="http://localhost/hook",
        GRAPH_CLIENT_STATE="short",
    )
    with pytest.raises(ConfigError) as exc:
        require_server(settings)
    message = exc.value.code if isinstance(exc.value.code, str) else str(exc.value)
    assert "GROQ_API_KEY" in message
    assert "GRAPH_WEBHOOK_URL" in message
    assert "GRAPH_CLIENT_STATE" in message


def test_load_settings_names_a_missing_client_id(monkeypatch):
    monkeypatch.delenv("MS_CLIENT_ID", raising=False)
    with pytest.raises(ConfigError) as exc:
        load_settings()
    message = exc.value.code if isinstance(exc.value.code, str) else str(exc.value)
    assert "MS_CLIENT_ID" in message


def test_workbook_path_rejects_traversal(tmp_path):
    with pytest.raises(ValidationError):
        settings_for(tmp_path, ONEDRIVE_XLSX_PATH="../secret.xlsx")


def test_authority_must_be_microsoft(tmp_path):
    with pytest.raises(ValidationError):
        settings_for(tmp_path, MS_AUTHORITY="https://example.com/consumers")


def test_settings_class_default_mailbox():
    assert Settings.model_fields["MAILBOX_ADDRESS"].default == "smc.scribe@outlook.com"
