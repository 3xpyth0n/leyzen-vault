"""Cache service for Leyzen Vault."""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from flask import current_app


class CacheService:
    """Simple in-memory cache service with TTL support."""

    def __init__(self, default_ttl: int = 300):
        """Initialize cache service.

        Args:
            default_ttl: Default TTL in seconds (default: 5 minutes)
        """
        self._cache: dict[str, tuple[Any, float]] = {}
        self.default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or expired
        """
        if key not in self._cache:
            return None

        value, expiry = self._cache[key]
        if time.time() > expiry:
            del self._cache[key]
            return None

        return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (None for default)
        """
        ttl = ttl or self.default_ttl
        expiry = time.time() + ttl
        self._cache[key] = (value, expiry)

    def delete(self, key: str) -> None:
        """Delete value from cache.

        Args:
            key: Cache key
        """
        if key in self._cache:
            del self._cache[key]

    def clear(self) -> None:
        """Clear all cache."""
        self._cache.clear()

    def get_or_set(
        self, key: str, func: Callable[[], Any], ttl: int | None = None
    ) -> Any:
        """Get value from cache or set it using a function.

        Args:
            key: Cache key
            func: Function to call if value not in cache
            ttl: TTL in seconds (None for default)

        Returns:
            Cached or computed value
        """
        value = self.get(key)
        if value is None:
            value = func()
            self.set(key, value, ttl)
        return value

    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching a pattern.

        Args:
            pattern: Pattern to match (simple substring match)

        Returns:
            Number of entries invalidated
        """
        keys_to_delete = [key for key in self._cache.keys() if pattern in key]
        for key in keys_to_delete:
            del self._cache[key]
        return len(keys_to_delete)


# Global cache instance
_cache_service: CacheService | None = None


def get_cache_service() -> CacheService:
    """Get global cache service instance."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


def cache_key(*parts: str) -> str:
    """Generate cache key from parts.

    Args:
        *parts: Key parts

    Returns:
        Cache key string
    """
    return ":".join(str(part) for part in parts)
