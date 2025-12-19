"""Request caching for ccproxy.

This module provides response caching for identical prompts,
duplicate request detection, and cache invalidation strategies.
"""

import hashlib
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached response entry."""

    response: dict[str, Any]
    created_at: float
    expires_at: float
    hit_count: int = 0
    model: str = ""
    prompt_hash: str = ""


@dataclass
class CacheStats:
    """Cache statistics."""

    total_entries: int
    hits: int
    misses: int
    hit_rate: float
    evictions: int
    memory_bytes: int


class RequestCache:
    """Thread-safe LRU cache for LLM responses.

    Features:
    - Duplicate request detection
    - Response caching for identical prompts
    - TTL-based expiration
    - LRU eviction when cache is full
    - Per-model caching
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 3600.0,  # 1 hour
        enabled: bool = True,
    ) -> None:
        """Initialize the cache.

        Args:
            max_size: Maximum number of cached entries
            default_ttl: Default time-to-live in seconds
            enabled: Whether caching is enabled
        """
        self._lock = threading.Lock()
        self._cache: dict[str, CacheEntry] = {}
        self._access_order: list[str] = []  # For LRU eviction
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._enabled = enabled

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @property
    def enabled(self) -> bool:
        """Check if cache is enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Enable or disable the cache."""
        self._enabled = value

    def _generate_key(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **params: Any,
    ) -> str:
        """Generate a cache key from request parameters.

        Args:
            model: Model name
            messages: List of messages
            **params: Additional parameters to include in key

        Returns:
            SHA256 hash of the request
        """
        # Create a deterministic string representation
        key_parts = [
            f"model:{model}",
            f"messages:{str(messages)}",
        ]

        # Include relevant params (exclude non-deterministic ones)
        for k, v in sorted(params.items()):
            if k not in ("stream", "timeout", "request_timeout"):
                key_parts.append(f"{k}:{v}")

        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _evict_expired(self) -> int:
        """Remove expired entries. Must be called with lock held."""
        now = time.time()
        expired = [k for k, v in self._cache.items() if v.expires_at < now]

        for key in expired:
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            self._evictions += 1

        return len(expired)

    def _evict_lru(self) -> None:
        """Evict least recently used entry. Must be called with lock held."""
        if self._access_order:
            oldest_key = self._access_order.pop(0)
            if oldest_key in self._cache:
                del self._cache[oldest_key]
                self._evictions += 1

    def get(
        self,
        model: str,
        messages: list[dict[str, Any]],
        **params: Any,
    ) -> dict[str, Any] | None:
        """Get cached response if available.

        Args:
            model: Model name
            messages: List of messages
            **params: Additional parameters

        Returns:
            Cached response or None if not found
        """
        if not self._enabled:
            return None

        key = self._generate_key(model, messages, **params)

        with self._lock:
            # Clean up expired entries periodically
            self._evict_expired()

            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            # Check if expired
            if entry.expires_at < time.time():
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                self._misses += 1
                return None

            # Update access order for LRU
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

            entry.hit_count += 1
            self._hits += 1

            logger.debug(f"Cache hit for model {model} (hits: {entry.hit_count})")
            return entry.response

    def set(
        self,
        model: str,
        messages: list[dict[str, Any]],
        response: dict[str, Any],
        ttl: float | None = None,
        **params: Any,
    ) -> str:
        """Cache a response.

        Args:
            model: Model name
            messages: List of messages
            response: Response to cache
            ttl: Optional custom TTL in seconds
            **params: Additional parameters

        Returns:
            Cache key
        """
        if not self._enabled:
            return ""

        key = self._generate_key(model, messages, **params)
        ttl = ttl if ttl is not None else self._default_ttl
        now = time.time()

        with self._lock:
            # Evict if at capacity
            while len(self._cache) >= self._max_size:
                self._evict_lru()

            # Clean up expired entries
            self._evict_expired()

            entry = CacheEntry(
                response=response,
                created_at=now,
                expires_at=now + ttl,
                model=model,
                prompt_hash=key[:16],
            )

            self._cache[key] = entry
            self._access_order.append(key)

            logger.debug(f"Cached response for model {model} (TTL: {ttl}s)")

        return key

    def invalidate(
        self,
        model: str | None = None,
        key: str | None = None,
    ) -> int:
        """Invalidate cache entries.

        Args:
            model: Invalidate all entries for this model
            key: Invalidate specific key

        Returns:
            Number of entries invalidated
        """
        with self._lock:
            if key:
                if key in self._cache:
                    del self._cache[key]
                    if key in self._access_order:
                        self._access_order.remove(key)
                    return 1
                return 0

            if model:
                to_remove = [k for k, v in self._cache.items() if v.model == model]
                for k in to_remove:
                    del self._cache[k]
                    if k in self._access_order:
                        self._access_order.remove(k)
                return len(to_remove)

            # Clear all
            count = len(self._cache)
            self._cache.clear()
            self._access_order.clear()
            return count

    def get_stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            CacheStats with current values
        """
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0

            # Estimate memory usage (rough approximation)
            memory = sum(
                len(str(entry.response)) for entry in self._cache.values()
            )

            return CacheStats(
                total_entries=len(self._cache),
                hits=self._hits,
                misses=self._misses,
                hit_rate=hit_rate,
                evictions=self._evictions,
                memory_bytes=memory,
            )

    def reset_stats(self) -> None:
        """Reset hit/miss statistics."""
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._evictions = 0


# Global cache instance
_cache_instance: RequestCache | None = None
_cache_lock = threading.Lock()


def get_cache() -> RequestCache:
    """Get the global request cache instance.

    Returns:
        The singleton RequestCache instance
    """
    global _cache_instance

    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:
                _cache_instance = RequestCache()

    return _cache_instance


def reset_cache() -> None:
    """Reset the global cache instance."""
    global _cache_instance
    with _cache_lock:
        _cache_instance = None


def cache_response_hook(
    data: dict[str, Any],
    user_api_key_dict: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    """Hook to check cache before request.

    If a cached response exists, it will be added to the request metadata
    for the handler to use.

    Args:
        data: Request data
        user_api_key_dict: User API key metadata
        **kwargs: Additional arguments

    Returns:
        Modified request data
    """
    cache = get_cache()
    if not cache.enabled:
        return data

    model = data.get("model", "")
    messages = data.get("messages", [])

    # Check cache
    cached_response = cache.get(model, messages)
    if cached_response:
        # Mark request as having cached response
        if "metadata" not in data:
            data["metadata"] = {}
        data["metadata"]["ccproxy_cached_response"] = cached_response
        data["metadata"]["ccproxy_cache_hit"] = True

        logger.info(f"Using cached response for model {model}")

    return data
