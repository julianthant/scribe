import logging

from app.auth.provider import TokenProvider
from app.core.logging import RedactFilter
from tests.helpers import settings_for


class _Response:
    def __init__(self, payload: dict) -> None:
        self.status_code = 200
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def test_access_token_stays_in_memory(tmp_path, monkeypatch):
    settings = settings_for(tmp_path, GOOGLE_REFRESH_TOKEN="stored-secret")
    calls = {"n": 0}

    def fake_post(url, data, timeout):
        calls["n"] += 1
        assert data["refresh_token"] == "stored-secret"
        return _Response({"access_token": "ya29.secret", "expires_in": 3600})

    monkeypatch.setattr("app.auth.provider.httpx.post", fake_post)
    provider = TokenProvider(settings)
    assert provider.access_token() == "ya29.secret"
    assert provider.access_token() == "ya29.secret"
    assert calls["n"] == 1
    assert not (tmp_path / "google_token.json").exists()


def test_rotated_credential_stays_in_memory_and_is_not_logged(tmp_path, monkeypatch, caplog):
    settings = settings_for(tmp_path, GOOGLE_REFRESH_TOKEN="stored-secret")
    seen: list[str] = []

    def fake_post(url, data, timeout):
        seen.append(data["refresh_token"])
        return _Response(
            {
                "access_token": "ya29.secret",
                "expires_in": 3600,
                "refresh_token": "rotated-secret",
            }
        )

    monkeypatch.setattr("app.auth.provider.httpx.post", fake_post)
    provider = TokenProvider(settings)
    caplog.set_level(logging.WARNING)
    assert provider.access_token() == "ya29.secret"
    assert provider.access_token(force=True) == "ya29.secret"
    assert seen == ["stored-secret", "rotated-secret"]
    assert "rotated-secret" not in caplog.text
    assert "stored-secret" not in caplog.text
    assert "replacement credential" in caplog.text


def test_redact_filter_hides_bearer_tokens():
    record = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Authorization Bearer super-secret-token",
        args=(),
        exc_info=None,
    )
    assert RedactFilter().filter(record) is True
    assert "super-secret-token" not in record.getMessage()
    assert "redacted" in record.getMessage()
