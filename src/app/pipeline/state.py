import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS subscription (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    subscription_id TEXT NOT NULL,
                    expiration TEXT
                )
                """
            )

    def get(self, message_id: str) -> tuple[str, int] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT status, attempts FROM messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
        if row is None:
            return None
        return str(row[0]), int(row[1])

    def mark(self, message_id: str, status: str, attempts: int) -> None:
        now = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO messages (message_id, status, attempts, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET
                    status = excluded.status,
                    attempts = excluded.attempts,
                    updated_at = excluded.updated_at
                """,
                (message_id, status, attempts, now),
            )

    def subscription_id(self) -> str | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT subscription_id FROM subscription WHERE id = 1"
            ).fetchone()
        if row is None:
            return None
        return str(row[0])

    def save_subscription(self, subscription_id: str, expiration: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO subscription (id, subscription_id, expiration)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    subscription_id = excluded.subscription_id,
                    expiration = excluded.expiration
                """,
                (subscription_id, expiration),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection
