import os
from pathlib import Path

from msal import SerializableTokenCache


def load_cache(path: Path) -> SerializableTokenCache:
    cache = SerializableTokenCache()
    if path.exists():
        cache.deserialize(path.read_text(encoding="utf-8"))
    return cache


def save_cache(path: Path, cache: SerializableTokenCache) -> None:
    """Persist the MSAL cache. Refresh-token rotation updates this file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(cache.serialize(), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)
