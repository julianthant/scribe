import logging

from app.auth.tokenstore import save_token
from app.core.logging import RedactFilter


def test_token_file_is_mode_600(tmp_path):
    path = tmp_path / "nested" / "google_token.json"
    save_token(path, {"refresh_token": "stored-secret", "access_token": "ya29.secret"})
    assert path.stat().st_mode & 0o777 == 0o600
    assert "stored-secret" in path.read_text(encoding="utf-8")


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
