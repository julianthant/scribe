import pytest
from pydantic import ValidationError

from app.core.config import ConfigError, Settings, load_settings, require_server
from tests.helpers import settings_for


def test_default_label_is_scribe_processed():
    assert Settings.model_fields["GMAIL_LABEL"].default == "scribe/processed"


def test_require_server_names_each_problem(tmp_path):
    settings = settings_for(
        tmp_path,
        GROQ_API_KEY="",
        GOOGLE_CLIENT_SECRET="",
        MAILBOX_ADDRESS="",
        GOOGLE_SHEET_ID="",
        WEBHOOK_SECRET="short",
    )
    with pytest.raises(ConfigError) as exc:
        require_server(settings)
    message = exc.value.code if isinstance(exc.value.code, str) else str(exc.value)
    assert "GROQ_API_KEY" in message
    assert "GOOGLE_CLIENT_SECRET" in message
    assert "MAILBOX_ADDRESS" in message
    assert "GOOGLE_SHEET_ID" in message
    assert "WEBHOOK_SECRET" in message


def test_load_settings_names_a_missing_client_id(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    with pytest.raises(ConfigError) as exc:
        load_settings()
    message = exc.value.code if isinstance(exc.value.code, str) else str(exc.value)
    assert "GOOGLE_CLIENT_ID" in message


def test_sheet_id_rejects_a_url(tmp_path):
    with pytest.raises(ValidationError):
        settings_for(tmp_path, GOOGLE_SHEET_ID="https://docs.google.com/spreadsheets")


def test_mailbox_must_look_like_an_email(tmp_path):
    with pytest.raises(ValidationError):
        settings_for(tmp_path, MAILBOX_ADDRESS="not-an-email")
