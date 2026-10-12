import logging

from msal import SerializableTokenCache

from app.auth.cache import save_cache
from app.core.logging import RedactFilter


def test_token_cache_is_mode_600(tmp_path):
    path = tmp_path / "nested" / "token_cache.json"
    save_cache(path, SerializableTokenCache())
    assert path.stat().st_mode & 0o777 == 0o600


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
