import threading


class StateStore:
    """Attempt counts for this process. The sheet message_id column is durable dedup."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: dict[str, tuple[str, int]] = {}

    def get(self, message_id: str) -> tuple[str, int] | None:
        with self._lock:
            return self._rows.get(message_id)

    def mark(self, message_id: str, status: str, attempts: int) -> None:
        with self._lock:
            self._rows[message_id] = (status, attempts)
