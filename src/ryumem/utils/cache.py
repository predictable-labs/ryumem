"""
Simple in-memory cache with TTL and LRU eviction.
Caches expensive operations like LLM calls and embeddings.
"""

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LRUCache:
    """
    Thread-safe LRU cache with TTL (time-to-live) support.

    Used to cache:
    - Entity extraction results
    - Relationship extraction results
    - Embedding vectors
    - Entity summaries
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """
        Initialize cache.

        Args:
            max_size: Maximum number of items in cache (LRU eviction when exceeded)
            ttl_seconds: Time-to-live in seconds (default: 1 hour)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self.lock = threading.Lock()
        self.hits = 0
        self.misses = 0

        logger.info(f"Initialized LRUCache with max_size={max_size}, ttl={ttl_seconds}s")

    def _make_key(self, *args: Any, **kwargs: Any) -> str:
        """
        Create a cache key from arguments.

        Args:
            args: Positional arguments to hash
            kwargs: Keyword arguments to hash

        Returns:
            Hash string suitable as cache key
        """
        # Combine args and kwargs into a single string
        key_parts = [str(arg) for arg in args]
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_string = "|".join(key_parts)

        # Hash to create fixed-size key
        return hashlib.sha256(key_string.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache if it exists and hasn't expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self.lock:
            if key not in self.cache:
                self.misses += 1
                return None

            value, timestamp = self.cache[key]

            # Check if expired
            if time.time() - timestamp > self.ttl_seconds:
                logger.debug(f"Cache key expired: {key[:16]}...")
                del self.cache[key]
                self.misses += 1
                return None

            # Move to end (mark as recently used)
            self.cache.move_to_end(key)
            self.hits += 1
            logger.debug(f"Cache HIT: {key[:16]}... (hits={self.hits}, misses={self.misses})")
            return value

    def set(self, key: str, value: Any) -> None:
        """
        Store value in cache with current timestamp.

        Args:
            key: Cache key
            value: Value to cache
        """
        with self.lock:
            # If key exists, remove it first
            if key in self.cache:
                del self.cache[key]

            # Add new entry
            self.cache[key] = (value, time.time())

            # Move to end (mark as recently used)
            self.cache.move_to_end(key)

            # Evict oldest item if cache is full
            if len(self.cache) > self.max_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                logger.debug(f"Cache evicted oldest key: {oldest_key[:16]}...")

            logger.debug(f"Cache SET: {key[:16]}... (size={len(self.cache)}/{self.max_size})")

    def clear(self) -> None:
        """Clear all cache entries."""
        with self.lock:
            size = len(self.cache)
            self.cache.clear()
            self.hits = 0
            self.misses = 0
            logger.info(f"Cache cleared ({size} entries removed)")

    def stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        with self.lock:
            total_requests = self.hits + self.misses
            hit_rate = self.hits / total_requests if total_requests > 0 else 0

            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": hit_rate,
                "ttl_seconds": self.ttl_seconds,
            }


# Global cache instances for different use cases
entity_extraction_cache = LRUCache(max_size=500, ttl_seconds=3600)  # 1 hour
relation_extraction_cache = LRUCache(max_size=500, ttl_seconds=3600)  # 1 hour
embedding_cache = LRUCache(max_size=2000, ttl_seconds=7200)  # 2 hours (embeddings are stable)
summary_cache = LRUCache(max_size=1000, ttl_seconds=1800)  # 30 minutes (summaries update frequently)


def get_cache_stats() -> dict[str, Any]:
    """
    Get statistics for all cache instances.

    Returns:
        Dictionary with stats for each cache
    """
    return {
        "entity_extraction": entity_extraction_cache.stats(),
        "relation_extraction": relation_extraction_cache.stats(),
        "embedding": embedding_cache.stats(),
        "summary": summary_cache.stats(),
    }


def clear_all_caches() -> None:
    """Clear all cache instances."""
    entity_extraction_cache.clear()
    relation_extraction_cache.clear()
    embedding_cache.clear()
    summary_cache.clear()
    logger.info("All caches cleared")
