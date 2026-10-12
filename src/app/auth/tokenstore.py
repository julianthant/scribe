import json
import os
from pathlib import Path


def load_token(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise AuthError("Token file is unreadable. Run scribe-login again.") from None
    if not isinstance(payload, dict):
        raise AuthError("Token file is unreadable. Run scribe-login again.")
    return payload


def save_token(path: Path, payload: dict) -> None:
    """Persist the Google refresh token. The file mode is 600."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)


class AuthError(RuntimeError):
    pass
