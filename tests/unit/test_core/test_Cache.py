"""
Unit tests for app.core.Cache module.

Tests cover:
- MemoryCache class functionality
- SharedMailboxCache class functionality
- Global cache instances and functions
- LRU eviction and TTL expiration
- Statistics tracking and cache metrics
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from app.core.Cache import (
    CacheEntry, 
    MemoryCache, 
    SharedMailboxCache,
    get_cache,
    get_shared_mailbox_cache,
    cleanup_expired_entries,
    get_cache_metrics,
    warmup_cache
)


class TestCacheEntry:
    """Test CacheEntry dataclass functionality."""

    def test_cache_entry_initialization(self):
        """Test CacheEntry initialization with default values."""
        entry = CacheEntry(
            value="test_value",
            timestamp=1234567890.0,
            ttl=300.0
        )
        
        assert entry.value == "test_value"
        assert entry.timestamp == 1234567890.0
        assert entry.ttl == 300.0
        assert entry.access_count == 0
        assert entry.last_accessed == 0

    @patch('time.time', return_value=1234567890.0 + 400)  # 400 seconds later
    def test_is_expired_true(self):
        """Test is_expired returns True when TTL exceeded."""
        entry = CacheEntry(
            value="test_value",
            timestamp=1234567890.0,
            ttl=300.0
        )
        
        assert entry.is_expired() is True

    @patch('time.time', return_value=1234567890.0 + 200)  # 200 seconds later
    def test_is_expired_false(self):
        """Test is_expired returns False when within TTL."""
        entry = CacheEntry(
            value="test_value",
            timestamp=1234567890.0,
            ttl=300.0
        )
        
        assert entry.is_expired() is False

    @patch('time.time', return_value=1234568000.0)
    def test_access_updates_metadata(self):
        """Test access method updates access count and timestamp."""
        entry = CacheEntry(
            value="test_value",
            timestamp=1234567890.0,
            ttl=300.0
        )
        
        result = entry.access()
        
        assert result == "test_value"
        assert entry.access_count == 1
        assert entry.last_accessed == 1234568000.0
        
        # Test multiple accesses
        entry.access()
        assert entry.access_count == 2


class TestMemoryCache:
    """Test MemoryCache class functionality."""

    def test_initialization_default_values(self):
        """Test MemoryCache initialization with default values."""
        cache = MemoryCache()
        
        assert cache.default_ttl == 300
        assert cache.max_size == 1000
        assert len(cache._cache) == 0
        assert cache._stats["hits"] == 0
        assert cache._stats["misses"] == 0

    def test_initialization_custom_values(self):
        """Test MemoryCache initialization with custom values."""
        cache = MemoryCache(default_ttl=600, max_size=500)
        
        assert cache.default_ttl == 600
        assert cache.max_size == 500

    @patch('time.time', return_value=1234567890.0)
    def test_set_and_get_success(self):
        """Test successful set and get operations."""
        cache = MemoryCache()
        
        cache.set("test_key", "test_value")
        result = cache.get("test_key")
        
        assert result == "test_value"
        assert cache._stats["sets"] == 1
        assert cache._stats["hits"] == 1
        assert cache._stats["misses"] == 0

    def test_get_nonexistent_key(self):
        """Test get operation with nonexistent key."""
        cache = MemoryCache()
        
        result = cache.get("nonexistent")
        
        assert result is None
        assert cache._stats["hits"] == 0
        assert cache._stats["misses"] == 1

    @patch('time.time', side_effect=[1234567890.0, 1234567890.0 + 400])  # Set, then get after expiry
    def test_get_expired_entry(self):
        """Test get operation with expired entry."""
        cache = MemoryCache(default_ttl=300)
        
        cache.set("test_key", "test_value")
        result = cache.get("test_key")
        
        assert result is None
        assert cache._stats["hits"] == 0
        assert cache._stats["misses"] == 1
        assert "test_key" not in cache._cache  # Should be removed

    def test_set_with_custom_ttl(self):
        """Test set operation with custom TTL."""
        cache = MemoryCache(default_ttl=300)
        
        with patch('time.time', return_value=1234567890.0):
            cache.set("test_key", "test_value", ttl=600)
        
        entry = cache._cache["test_key"]
        assert entry.ttl == 600

    def test_set_overwrites_existing_key(self):
        """Test set operation overwrites existing key."""
        cache = MemoryCache()
        
        with patch('time.time', return_value=1234567890.0):
            cache.set("test_key", "value1")
            cache.set("test_key", "value2")
        
        result = cache.get("test_key")
        assert result == "value2"
        assert cache._stats["sets"] == 2

    def test_lru_eviction(self):
        """Test LRU eviction when max_size is reached."""
        cache = MemoryCache(max_size=3)
        
        with patch('time.time', return_value=1234567890.0):
            cache.set("key1", "value1")
            cache.set("key2", "value2")
            cache.set("key3", "value3")
            # This should evict key1 (oldest)
            cache.set("key4", "value4")
        
        assert cache.get("key1") is None  # Evicted
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"
        assert cache._stats["evictions"] == 1

    def test_lru_ordering_on_access(self):
        """Test LRU ordering is maintained when accessing items."""
        cache = MemoryCache(max_size=3)
        
        with patch('time.time', return_value=1234567890.0):
            cache.set("key1", "value1")
            cache.set("key2", "value2") 
            cache.set("key3", "value3")
            
            # Access key1 to make it most recent
            cache.get("key1")
            
            # This should evict key2 (now oldest)
            cache.set("key4", "value4")
        
        assert cache.get("key1") == "value1"  # Not evicted due to recent access
        assert cache.get("key2") is None      # Evicted
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_delete_existing_key(self):
        """Test delete operation with existing key."""
        cache = MemoryCache()
        
        cache.set("test_key", "test_value")
        result = cache.delete("test_key")
        
        assert result is True
        assert cache.get("test_key") is None
        assert cache._stats["deletes"] == 1

    def test_delete_nonexistent_key(self):
        """Test delete operation with nonexistent key."""
        cache = MemoryCache()
        
        result = cache.delete("nonexistent")
        
        assert result is False
        assert cache._stats["deletes"] == 0

    def test_clear_all_entries(self):
        """Test clear operation removes all entries."""
        cache = MemoryCache()
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        
        assert len(cache._cache) == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    @patch('time.time', side_effect=[
        1234567890.0,  # key1 set
        1234567890.0,  # key2 set  
        1234567890.0,  # key3 set
        1234567890.0 + 400  # cleanup call (after 400 seconds)
    ])
    def test_cleanup_expired_entries(self):
        """Test cleanup removes expired entries."""
        cache = MemoryCache(default_ttl=300)
        
        cache.set("key1", "value1")  # Will expire
        cache.set("key2", "value2")  # Will expire
        cache.set("key3", "value3", ttl=600)  # Won't expire
        
        removed_count = cache.cleanup_expired()
        
        assert removed_count == 2
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"
        assert cache._stats["cleanups"] == 2

    def test_get_stats(self):
        """Test get_stats returns correct statistics."""
        cache = MemoryCache()
        
        cache.set("key1", "value1")
        cache.get("key1")  # Hit
        cache.get("nonexistent")  # Miss
        cache.delete("key1")
        
        stats = cache.get_stats()
        
        assert stats["total_entries"] == 0
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate_percent"] == 50.0
        assert stats["sets"] == 1
        assert stats["deletes"] == 1
        assert stats["cleanups"] == 0
        assert stats["evictions"] == 0

    def test_get_cache_info(self):
        """Test get_cache_info returns detailed information."""
        cache = MemoryCache()
        
        with patch('time.time', return_value=1234567890.0):
            cache.set("key1", "value1")
            cache.get("key1")  # Access to set last_accessed
        
        with patch('time.time', return_value=1234567890.0 + 100):
            info = cache.get_cache_info()
        
        assert "stats" in info
        assert "entries" in info
        assert "total_entries" in info
        assert len(info["entries"]) == 1
        
        entry_info = info["entries"][0]
        assert entry_info["key"] == "key1"
        assert entry_info["age_seconds"] == 100
        assert entry_info["access_count"] == 1


class TestSharedMailboxCache:
    """Test SharedMailboxCache class functionality."""

    def test_initialization(self):
        """Test SharedMailboxCache initialization."""
        memory_cache = MemoryCache()
        shared_cache = SharedMailboxCache(memory_cache)
        
        assert shared_cache.cache == memory_cache
        assert shared_cache.mailbox_ttl == 300
        assert shared_cache.message_ttl == 180
        assert shared_cache.folder_ttl == 600
        assert shared_cache.stats_ttl == 120

    def test_mailbox_key_generation(self):
        """Test mailbox cache key generation."""
        memory_cache = MemoryCache()
        shared_cache = SharedMailboxCache(memory_cache)
        
        key = shared_cache._mailbox_key("test@example.com")
        assert key == "mailbox:test@example.com"

    def test_messages_key_generation(self):
        """Test messages cache key generation."""
        memory_cache = MemoryCache()
        shared_cache = SharedMailboxCache(memory_cache)
        
        key_without_folder = shared_cache._messages_key("test@example.com")
        assert key_without_folder == "messages:test@example.com"
        
        key_with_folder = shared_cache._messages_key("test@example.com", "folder123")
        assert key_with_folder == "messages:test@example.com:folder123"

    def test_folders_key_generation(self):
        """Test folders cache key generation."""
        memory_cache = MemoryCache()
        shared_cache = SharedMailboxCache(memory_cache)
        
        key = shared_cache._folders_key("test@example.com")
        assert key == "folders:test@example.com"

    def test_stats_key_generation(self):
        """Test statistics cache key generation."""
        memory_cache = MemoryCache()
        shared_cache = SharedMailboxCache(memory_cache)
        
        key = shared_cache._stats_key("test@example.com")
        assert key == "stats:test@example.com"

    def test_voice_messages_key_generation(self):
        """Test voice messages cache key generation."""
        memory_cache = MemoryCache()
        shared_cache = SharedMailboxCache(memory_cache)
        
        key = shared_cache._voice_messages_key("test@example.com")
        assert key == "voice_messages:test@example.com"

    def test_get_set_mailbox(self):
        """Test mailbox get/set operations."""
        memory_cache = MemoryCache()
        shared_cache = SharedMailboxCache(memory_cache)
        
        mailbox_data = {"id": "123", "name": "Test Mailbox"}
        
        # Initially None
        assert shared_cache.get_mailbox("test@example.com") is None
        
        # Set and retrieve
        shared_cache.set_mailbox("test@example.com", mailbox_data)
        result = shared_cache.get_mailbox("test@example.com")
        
        assert result == mailbox_data

    def test_get_set_messages(self):
        """Test messages get/set operations."""
        memory_cache = MemoryCache()
        shared_cache = SharedMailboxCache(memory_cache)
        
        messages_data = [{"id": "msg1"}, {"id": "msg2"}]
        
        # Test without folder
        shared_cache.set_messages("test@example.com", messages_data)
        result = shared_cache.get_messages("test@example.com")
        assert result == messages_data
        
        # Test with folder
        folder_messages = [{"id": "msg3"}]
        shared_cache.set_messages("test@example.com", folder_messages, "folder123")
        result = shared_cache.get_messages("test@example.com", "folder123")
        assert result == folder_messages

    def test_get_set_folders(self):
        """Test folders get/set operations."""
        memory_cache = MemoryCache()
        shared_cache = SharedMailboxCache(memory_cache)
        
        folders_data = [{"id": "folder1"}, {"id": "folder2"}]
        
        shared_cache.set_folders("test@example.com", folders_data)
        result = shared_cache.get_folders("test@example.com")
        
        assert result == folders_data

    def test_get_set_statistics(self):
        """Test statistics get/set operations."""
        memory_cache = MemoryCache()
        shared_cache = SharedMailboxCache(memory_cache)
        
        stats_data = {"total_messages": 100, "unread": 5}
        
        shared_cache.set_statistics("test@example.com", stats_data)
        result = shared_cache.get_statistics("test@example.com")
        
        assert result == stats_data

    def test_get_set_voice_messages(self):
        """Test voice messages get/set operations."""
        memory_cache = MemoryCache()
        shared_cache = SharedMailboxCache(memory_cache)
        
        voice_data = [{"id": "voice1"}, {"id": "voice2"}]
        
        shared_cache.set_voice_messages("test@example.com", voice_data)
        result = shared_cache.get_voice_messages("test@example.com")
        
        assert result == voice_data

    def test_invalidate_mailbox(self):
        """Test invalidate_mailbox removes all related data."""
        memory_cache = MemoryCache()
        shared_cache = SharedMailboxCache(memory_cache)
        
        # Set various data types
        shared_cache.set_mailbox("test@example.com", {"id": "123"})
        shared_cache.set_messages("test@example.com", [{"id": "msg1"}])
        shared_cache.set_folders("test@example.com", [{"id": "folder1"}])
        shared_cache.set_statistics("test@example.com", {"total": 10})
        shared_cache.set_voice_messages("test@example.com", [{"id": "voice1"}])
        
        # Invalidate all
        shared_cache.invalidate_mailbox("test@example.com")
        
        # All should be None
        assert shared_cache.get_mailbox("test@example.com") is None
        assert shared_cache.get_messages("test@example.com") is None
        assert shared_cache.get_folders("test@example.com") is None
        assert shared_cache.get_statistics("test@example.com") is None
        assert shared_cache.get_voice_messages("test@example.com") is None

    def test_get_cache_status(self):
        """Test get_cache_status returns comprehensive status."""
        memory_cache = MemoryCache()
        shared_cache = SharedMailboxCache(memory_cache)
        
        # Add data of different types
        shared_cache.set_mailbox("test1@example.com", {"id": "123"})
        shared_cache.set_mailbox("test2@example.com", {"id": "456"})
        shared_cache.set_messages("test1@example.com", [{"id": "msg1"}])
        shared_cache.set_folders("test1@example.com", [{"id": "folder1"}])
        shared_cache.set_statistics("test1@example.com", {"total": 10})
        shared_cache.set_voice_messages("test1@example.com", [{"id": "voice1"}])
        
        status = shared_cache.get_cache_status()
        
        assert "overall_stats" in status
        assert "entry_counts" in status
        assert "ttl_settings" in status
        
        counts = status["entry_counts"]
        assert counts["mailboxes"] == 2
        assert counts["messages"] == 1
        assert counts["folders"] == 1
        assert counts["statistics"] == 1
        assert counts["voice_messages"] == 1
        
        ttl = status["ttl_settings"]
        assert ttl["mailbox_ttl"] == 300
        assert ttl["message_ttl"] == 180


class TestGlobalCacheFunctions:
    """Test global cache functions and instances."""

    @patch('app.core.Cache.settings')
    def test_get_cache_returns_global_instance(self, mock_settings):
        """Test get_cache returns the global memory cache instance."""
        mock_settings.get.side_effect = lambda key, default: {
            "cache_default_ttl": default,
            "cache_max_size": default
        }.get(key, default)
        
        cache = get_cache()
        assert isinstance(cache, MemoryCache)
        
        # Should return the same instance
        cache2 = get_cache()
        assert cache is cache2

    def test_get_shared_mailbox_cache_returns_global_instance(self):
        """Test get_shared_mailbox_cache returns the global instance."""
        cache = get_shared_mailbox_cache()
        assert isinstance(cache, SharedMailboxCache)
        
        # Should return the same instance
        cache2 = get_shared_mailbox_cache()
        assert cache is cache2

    @patch('app.core.Cache._memory_cache')
    def test_cleanup_expired_entries(self, mock_cache):
        """Test cleanup_expired_entries calls global cache cleanup."""
        mock_cache.cleanup_expired.return_value = 5
        
        result = cleanup_expired_entries()
        
        assert result == 5
        mock_cache.cleanup_expired.assert_called_once()

    @patch('app.core.Cache._memory_cache')
    @patch('app.core.Cache.shared_mailbox_cache')
    @patch('app.core.Cache.settings')
    def test_get_cache_metrics(self, mock_settings, mock_shared_cache, mock_memory_cache):
        """Test get_cache_metrics returns comprehensive metrics."""
        mock_settings.get.return_value = 180
        mock_memory_cache.get_stats.return_value = {"hits": 10, "misses": 5}
        mock_shared_cache.get_cache_status.return_value = {"total": 15}
        
        metrics = get_cache_metrics()
        
        assert "memory_cache" in metrics
        assert "shared_mailbox_cache" in metrics
        assert "cleanup_interval" in metrics
        assert metrics["memory_cache"]["hits"] == 10
        assert metrics["cleanup_interval"] == 180

    @patch('app.core.Cache._memory_cache')
    @patch('app.core.Cache.shared_mailbox_cache')
    def test_warmup_cache(self, mock_shared_cache, mock_memory_cache):
        """Test warmup_cache initializes cache structures."""
        mock_memory_cache.get_stats.return_value = {}
        mock_shared_cache.get_cache_status.return_value = {}
        
        warmup_cache()
        
        mock_memory_cache.get_stats.assert_called_once()
        mock_shared_cache.get_cache_status.assert_called_once()


class TestCacheIntegration:
    """Integration tests for cache components working together."""

    def test_memory_cache_with_shared_mailbox_cache(self):
        """Test MemoryCache and SharedMailboxCache integration."""
        memory_cache = MemoryCache(max_size=10, default_ttl=300)
        shared_cache = SharedMailboxCache(memory_cache)
        
        # Set data through shared cache
        shared_cache.set_mailbox("test@example.com", {"id": "123"})
        shared_cache.set_messages("test@example.com", [{"id": "msg1"}])
        
        # Verify it's in the underlying memory cache
        mailbox_key = shared_cache._mailbox_key("test@example.com")
        messages_key = shared_cache._messages_key("test@example.com")
        
        assert memory_cache.get(mailbox_key) is not None
        assert memory_cache.get(messages_key) is not None
        
        # Verify stats are updated
        stats = memory_cache.get_stats()
        assert stats["sets"] == 2
        assert stats["total_entries"] == 2

    def test_cache_size_limits_across_mailboxes(self):
        """Test cache size limits work across multiple mailboxes."""
        memory_cache = MemoryCache(max_size=5)  # Small cache
        shared_cache = SharedMailboxCache(memory_cache)
        
        # Add data that will exceed the limit
        for i in range(3):
            email = f"test{i}@example.com"
            shared_cache.set_mailbox(email, {"id": f"{i}"})
            shared_cache.set_messages(email, [{"id": f"msg{i}"}])
        
        # This should trigger eviction
        shared_cache.set_folders("test3@example.com", [{"id": "folder"}])
        
        # Some earlier entries should be evicted
        stats = memory_cache.get_stats()
        assert stats["total_entries"] == 5  # At max capacity
        assert stats["evictions"] > 0

    @patch('time.time', side_effect=[
        1234567890.0,  # Set time
        1234567890.0 + 400  # Cleanup time (after TTL)
    ])
    def test_shared_cache_ttl_expiration(self, mock_time):
        """Test TTL expiration works through SharedMailboxCache."""
        memory_cache = MemoryCache()
        shared_cache = SharedMailboxCache(memory_cache)
        
        # Set data with different TTLs
        shared_cache.set_mailbox("test@example.com", {"id": "123"})  # TTL=300
        shared_cache.set_messages("test@example.com", [{"id": "msg1"}])  # TTL=180
        shared_cache.set_folders("test@example.com", [{"id": "folder1"}])  # TTL=600
        
        # After 400 seconds, mailbox and messages should expire, folders should not
        assert shared_cache.get_mailbox("test@example.com") is None
        assert shared_cache.get_messages("test@example.com") is None
        assert shared_cache.get_folders("test@example.com") is not None