import logging
import re

_TOKEN_PATTERN = re.compile(
    r"(Bearer\s+)\S+|access_token|refresh_token|client_secret|ya29\.[A-Za-z0-9_\-]+",
    re.IGNORECASE,
)


class RedactFilter(logging.Filter):
    """Drop log lines that would reveal tokens. Transcripts are never logged by callers."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if _TOKEN_PATTERN.search(message):
            record.msg = "redacted log line that contained a token"
            record.args = ()
        return True


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    root = logging.getLogger()
    _install_redaction(root)
    for handler in root.handlers:
        _install_redaction(handler)
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


def _install_redaction(target: logging.Logger | logging.Handler) -> None:
    if any(isinstance(item, RedactFilter) for item in target.filters):
        return
    target.addFilter(RedactFilter())
