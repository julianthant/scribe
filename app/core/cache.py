"""
Caching utilities for the Scribe application.
Provides in-memory caching for shared mailbox data and other frequently accessed items.
"""

import time
import logging
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with value and metadata."""
    value: Any
    timestamp: float
    ttl: float
    access_count: int = 0
    last_accessed: float = 0

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return time.time() - self.timestamp > self.ttl

    def access(self) -> Any:
        """Access the cached value and update access metadata."""
        self.access_count += 1
        self.last_accessed = time.time()
        return self.value


class MemoryCache:
    """Simple in-memory cache with TTL support."""

    def __init__(self, default_ttl: float = 300):
        """Initialize memory cache.
        
        Args:
            default_ttl: Default time-to-live in seconds (5 minutes)
        """
        self._cache: Dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "cleanups": 0
        }

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value if exists and not expired, None otherwise
        """
        if key not in self._cache:
            self._stats["misses"] += 1
            return None

        entry = self._cache[key]
        
        if entry.is_expired():
            del self._cache[key]
            self._stats["misses"] += 1
            return None

        self._stats["hits"] += 1
        return entry.access()

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        if ttl is None:
            ttl = self.default_ttl

        self._cache[key] = CacheEntry(
            value=value,
            timestamp=time.time(),
            ttl=ttl
        )
        self._stats["sets"] += 1

    def delete(self, key: str) -> bool:
        """Delete value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key was deleted, False if key didn't exist
        """
        if key in self._cache:
            del self._cache[key]
            self._stats["deletes"] += 1
            return True
        return False

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()
        logger.info("Cache cleared")

    def cleanup_expired(self) -> int:
        """Remove expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        current_time = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if current_time - entry.timestamp > entry.ttl
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            self._stats["cleanups"] += len(expired_keys)
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "total_entries": len(self._cache),
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate_percent": round(hit_rate, 2),
            "sets": self._stats["sets"],
            "deletes": self._stats["deletes"],
            "cleanups": self._stats["cleanups"],
            "memory_usage_entries": len(self._cache)
        }

    def get_cache_info(self) -> Dict[str, Any]:
        """Get detailed cache information.
        
        Returns:
            Detailed cache information including entry details
        """
        current_time = time.time()
        entries_info = []
        
        for key, entry in self._cache.items():
            entries_info.append({
                "key": key,
                "size_estimate": len(str(entry.value)),
                "age_seconds": current_time - entry.timestamp,
                "ttl_seconds": entry.ttl,
                "expires_in_seconds": max(0, entry.ttl - (current_time - entry.timestamp)),
                "access_count": entry.access_count,
                "last_accessed": entry.last_accessed
            })
        
        # Sort by most recently accessed
        entries_info.sort(key=lambda x: x["last_accessed"], reverse=True)
        
        return {
            "stats": self.get_stats(),
            "entries": entries_info[:10],  # Top 10 most recent
            "total_entries": len(self._cache)
        }


class SharedMailboxCache:
    """Specialized cache for shared mailbox data."""

    def __init__(self, cache: MemoryCache):
        """Initialize shared mailbox cache.
        
        Args:
            cache: Memory cache instance
        """
        self.cache = cache
        self.mailbox_ttl = 300  # 5 minutes
        self.message_ttl = 180  # 3 minutes
        self.folder_ttl = 600   # 10 minutes
        self.stats_ttl = 120    # 2 minutes

    def _mailbox_key(self, email_address: str) -> str:
        """Generate cache key for mailbox data."""
        return f"mailbox:{email_address}"

    def _messages_key(self, email_address: str, folder_id: Optional[str] = None) -> str:
        """Generate cache key for messages."""
        folder_part = f":{folder_id}" if folder_id else ""
        return f"messages:{email_address}{folder_part}"

    def _folders_key(self, email_address: str) -> str:
        """Generate cache key for folders."""
        return f"folders:{email_address}"

    def _stats_key(self, email_address: str) -> str:
        """Generate cache key for statistics."""
        return f"stats:{email_address}"

    def _voice_messages_key(self, email_address: str) -> str:
        """Generate cache key for voice messages."""
        return f"voice_messages:{email_address}"

    def get_mailbox(self, email_address: str) -> Optional[Any]:
        """Get cached mailbox data."""
        return self.cache.get(self._mailbox_key(email_address))

    def set_mailbox(self, email_address: str, mailbox_data: Any) -> None:
        """Cache mailbox data."""
        self.cache.set(self._mailbox_key(email_address), mailbox_data, self.mailbox_ttl)

    def get_messages(self, email_address: str, folder_id: Optional[str] = None) -> Optional[Any]:
        """Get cached messages."""
        return self.cache.get(self._messages_key(email_address, folder_id))

    def set_messages(self, email_address: str, messages_data: Any, folder_id: Optional[str] = None) -> None:
        """Cache messages data."""
        self.cache.set(self._messages_key(email_address, folder_id), messages_data, self.message_ttl)

    def get_folders(self, email_address: str) -> Optional[Any]:
        """Get cached folders."""
        return self.cache.get(self._folders_key(email_address))

    def set_folders(self, email_address: str, folders_data: Any) -> None:
        """Cache folders data."""
        self.cache.set(self._folders_key(email_address), folders_data, self.folder_ttl)

    def get_statistics(self, email_address: str) -> Optional[Any]:
        """Get cached statistics."""
        return self.cache.get(self._stats_key(email_address))

    def set_statistics(self, email_address: str, stats_data: Any) -> None:
        """Cache statistics data."""
        self.cache.set(self._stats_key(email_address), stats_data, self.stats_ttl)

    def get_voice_messages(self, email_address: str) -> Optional[Any]:
        """Get cached voice messages."""
        return self.cache.get(self._voice_messages_key(email_address))

    def set_voice_messages(self, email_address: str, voice_messages_data: Any) -> None:
        """Cache voice messages data."""
        self.cache.set(self._voice_messages_key(email_address), voice_messages_data, self.message_ttl)

    def invalidate_mailbox(self, email_address: str) -> None:
        """Invalidate all cached data for a mailbox."""
        keys_to_delete = [
            self._mailbox_key(email_address),
            self._messages_key(email_address),
            self._folders_key(email_address),
            self._stats_key(email_address),
            self._voice_messages_key(email_address)
        ]
        
        for key in keys_to_delete:
            self.cache.delete(key)
        
        logger.info(f"Invalidated cache for mailbox {email_address}")

    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status for shared mailboxes."""
        stats = self.cache.get_stats()
        
        # Count entries by type
        mailbox_entries = 0
        message_entries = 0
        folder_entries = 0
        stats_entries = 0
        voice_entries = 0
        
        for key in self.cache._cache.keys():
            if key.startswith("mailbox:"):
                mailbox_entries += 1
            elif key.startswith("messages:"):
                message_entries += 1
            elif key.startswith("folders:"):
                folder_entries += 1
            elif key.startswith("stats:"):
                stats_entries += 1
            elif key.startswith("voice_messages:"):
                voice_entries += 1
        
        return {
            "overall_stats": stats,
            "entry_counts": {
                "mailboxes": mailbox_entries,
                "messages": message_entries,
                "folders": folder_entries,
                "statistics": stats_entries,
                "voice_messages": voice_entries
            },
            "ttl_settings": {
                "mailbox_ttl": self.mailbox_ttl,
                "message_ttl": self.message_ttl,
                "folder_ttl": self.folder_ttl,
                "stats_ttl": self.stats_ttl
            }
        }


# Global cache instances
_memory_cache = MemoryCache(default_ttl=300)
shared_mailbox_cache = SharedMailboxCache(_memory_cache)


def get_cache() -> MemoryCache:
    """Get the global memory cache instance."""
    return _memory_cache


def get_shared_mailbox_cache() -> SharedMailboxCache:
    """Get the shared mailbox cache instance."""
    return shared_mailbox_cache


def cleanup_expired_entries():
    """Cleanup expired entries from all caches."""
    expired_count = _memory_cache.cleanup_expired()
    if expired_count > 0:
        logger.info(f"Cleaned up {expired_count} expired cache entries")
    return expired_count