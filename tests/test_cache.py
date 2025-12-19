"""Tests for request caching functionality."""

import time

import pytest

from ccproxy.cache import (
    CacheEntry,
    CacheStats,
    RequestCache,
    cache_response_hook,
    get_cache,
    reset_cache,
)


class TestRequestCache:
    """Tests for RequestCache class."""

    def setup_method(self) -> None:
        """Reset cache before each test."""
        reset_cache()

    def test_cache_get_miss(self) -> None:
        """Test cache miss returns None."""
        cache = RequestCache()
        result = cache.get("gpt-4", [{"role": "user", "content": "Hello"}])
        assert result is None

    def test_cache_set_and_get(self) -> None:
        """Test caching and retrieving response."""
        cache = RequestCache()
        messages = [{"role": "user", "content": "Hello"}]
        response = {"choices": [{"message": {"content": "Hi!"}}]}

        cache.set("gpt-4", messages, response)
        result = cache.get("gpt-4", messages)

        assert result == response

    def test_cache_key_uniqueness(self) -> None:
        """Test that different requests have different keys."""
        cache = RequestCache()
        messages1 = [{"role": "user", "content": "Hello"}]
        messages2 = [{"role": "user", "content": "World"}]
        response1 = {"content": "response1"}
        response2 = {"content": "response2"}

        cache.set("gpt-4", messages1, response1)
        cache.set("gpt-4", messages2, response2)

        assert cache.get("gpt-4", messages1) == response1
        assert cache.get("gpt-4", messages2) == response2

    def test_cache_model_specific(self) -> None:
        """Test that cache is model-specific."""
        cache = RequestCache()
        messages = [{"role": "user", "content": "Hello"}]
        response1 = {"content": "gpt-4 response"}
        response2 = {"content": "claude response"}

        cache.set("gpt-4", messages, response1)
        cache.set("claude-3", messages, response2)

        assert cache.get("gpt-4", messages) == response1
        assert cache.get("claude-3", messages) == response2

    def test_cache_disabled(self) -> None:
        """Test cache when disabled."""
        cache = RequestCache(enabled=False)
        messages = [{"role": "user", "content": "Hello"}]

        key = cache.set("gpt-4", messages, {"content": "response"})
        result = cache.get("gpt-4", messages)

        assert key == ""
        assert result is None

    def test_cache_enable_disable(self) -> None:
        """Test enabling and disabling cache."""
        cache = RequestCache(enabled=True)
        assert cache.enabled is True

        cache.enabled = False
        assert cache.enabled is False


class TestCacheTTL:
    """Tests for cache TTL behavior."""

    def setup_method(self) -> None:
        """Reset cache before each test."""
        reset_cache()

    def test_cache_expires(self) -> None:
        """Test that cache entries expire."""
        cache = RequestCache(default_ttl=0.1)  # 100ms TTL
        messages = [{"role": "user", "content": "Hello"}]

        cache.set("gpt-4", messages, {"content": "response"})
        time.sleep(0.2)  # Wait for expiration

        result = cache.get("gpt-4", messages)
        assert result is None

    def test_cache_custom_ttl(self) -> None:
        """Test custom TTL per entry."""
        cache = RequestCache(default_ttl=10.0)
        messages = [{"role": "user", "content": "Hello"}]

        cache.set("gpt-4", messages, {"content": "response"}, ttl=0.1)
        time.sleep(0.2)

        result = cache.get("gpt-4", messages)
        assert result is None


class TestCacheLRU:
    """Tests for LRU eviction."""

    def setup_method(self) -> None:
        """Reset cache before each test."""
        reset_cache()

    def test_lru_eviction(self) -> None:
        """Test LRU eviction when cache is full."""
        cache = RequestCache(max_size=2)

        cache.set("gpt-4", [{"content": "1"}], {"resp": "1"})
        cache.set("gpt-4", [{"content": "2"}], {"resp": "2"})
        cache.set("gpt-4", [{"content": "3"}], {"resp": "3"})  # Should evict "1"

        assert cache.get("gpt-4", [{"content": "1"}]) is None
        assert cache.get("gpt-4", [{"content": "2"}]) is not None
        assert cache.get("gpt-4", [{"content": "3"}]) is not None

    def test_lru_access_updates_order(self) -> None:
        """Test that access updates LRU order."""
        cache = RequestCache(max_size=2)

        cache.set("gpt-4", [{"content": "1"}], {"resp": "1"})
        cache.set("gpt-4", [{"content": "2"}], {"resp": "2"})

        # Access "1" making it most recently used
        cache.get("gpt-4", [{"content": "1"}])

        # Add "3" - should evict "2" (now least recently used)
        cache.set("gpt-4", [{"content": "3"}], {"resp": "3"})

        assert cache.get("gpt-4", [{"content": "1"}]) is not None  # Still there
        assert cache.get("gpt-4", [{"content": "2"}]) is None  # Evicted


class TestCacheInvalidation:
    """Tests for cache invalidation."""

    def setup_method(self) -> None:
        """Reset cache before each test."""
        reset_cache()

    def test_invalidate_by_key(self) -> None:
        """Test invalidating specific key."""
        cache = RequestCache()
        messages = [{"role": "user", "content": "Hello"}]

        key = cache.set("gpt-4", messages, {"content": "response"})
        count = cache.invalidate(key=key)

        assert count == 1
        assert cache.get("gpt-4", messages) is None

    def test_invalidate_by_model(self) -> None:
        """Test invalidating all entries for a model."""
        cache = RequestCache()

        cache.set("gpt-4", [{"content": "1"}], {"resp": "1"})
        cache.set("gpt-4", [{"content": "2"}], {"resp": "2"})
        cache.set("claude-3", [{"content": "1"}], {"resp": "1"})

        count = cache.invalidate(model="gpt-4")

        assert count == 2
        assert cache.get("gpt-4", [{"content": "1"}]) is None
        assert cache.get("claude-3", [{"content": "1"}]) is not None

    def test_invalidate_all(self) -> None:
        """Test invalidating all entries."""
        cache = RequestCache()

        cache.set("gpt-4", [{"content": "1"}], {"resp": "1"})
        cache.set("claude-3", [{"content": "1"}], {"resp": "1"})

        count = cache.invalidate()

        assert count == 2
        stats = cache.get_stats()
        assert stats.total_entries == 0


class TestCacheStats:
    """Tests for cache statistics."""

    def setup_method(self) -> None:
        """Reset cache before each test."""
        reset_cache()

    def test_hit_miss_tracking(self) -> None:
        """Test hit and miss tracking."""
        cache = RequestCache()
        messages = [{"role": "user", "content": "Hello"}]

        # Miss
        cache.get("gpt-4", messages)

        # Set and hit
        cache.set("gpt-4", messages, {"content": "response"})
        cache.get("gpt-4", messages)
        cache.get("gpt-4", messages)

        stats = cache.get_stats()
        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.hit_rate == pytest.approx(2 / 3)

    def test_eviction_tracking(self) -> None:
        """Test eviction counting."""
        cache = RequestCache(max_size=1)

        cache.set("gpt-4", [{"content": "1"}], {"resp": "1"})
        cache.set("gpt-4", [{"content": "2"}], {"resp": "2"})  # Evicts 1

        stats = cache.get_stats()
        assert stats.evictions == 1

    def test_reset_stats(self) -> None:
        """Test resetting statistics."""
        cache = RequestCache()
        cache.get("gpt-4", [{"content": "test"}])  # Miss

        cache.reset_stats()

        stats = cache.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0


class TestCacheHook:
    """Tests for cache response hook."""

    def setup_method(self) -> None:
        """Reset cache before each test."""
        reset_cache()

    def test_hook_cache_miss(self) -> None:
        """Test hook on cache miss."""
        cache = get_cache()
        cache.enabled = True

        data = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
        }

        result = cache_response_hook(data, {})

        assert "ccproxy_cached_response" not in result.get("metadata", {})

    def test_hook_cache_hit(self) -> None:
        """Test hook on cache hit."""
        cache = get_cache()
        cache.enabled = True
        messages = [{"role": "user", "content": "Hello"}]
        response = {"choices": [{"message": {"content": "Hi!"}}]}

        cache.set("gpt-4", messages, response)

        data = {"model": "gpt-4", "messages": messages}
        result = cache_response_hook(data, {})

        assert result["metadata"]["ccproxy_cache_hit"] is True
        assert result["metadata"]["ccproxy_cached_response"] == response


class TestGlobalCache:
    """Tests for global cache instance."""

    def setup_method(self) -> None:
        """Reset cache before each test."""
        reset_cache()

    def test_get_cache_singleton(self) -> None:
        """Test get_cache returns singleton."""
        cache1 = get_cache()
        cache2 = get_cache()
        assert cache1 is cache2

    def test_reset_cache(self) -> None:
        """Test reset_cache creates new instance."""
        cache1 = get_cache()
        reset_cache()
        cache2 = get_cache()
        assert cache1 is not cache2
