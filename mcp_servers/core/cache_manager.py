"""
4-Tier Cache Manager for MCP servers.

Tiers:
  L1: LRUCache (in-memory, 100 items)
  L2: TTLCache (in-memory, 1000 items, 1hr default TTL)
  L3: DiskCache (SQLite-backed, persistent)

TTL by data type:
  - realtime: 60 seconds
  - daily_data: 3600 seconds (1 hour)
  - historical: 86400 seconds (24 hours)
  - static_meta: 604800 seconds (1 week)
"""
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Optional
from functools import wraps

from cachetools import LRUCache, TTLCache
import diskcache

logger = logging.getLogger(__name__)


class CacheManager:
    """Multi-tier cache manager."""

    TTL_CONFIG = {
        "realtime": 60,
        "daily_data": 3600,
        "historical": 86400,
        "static_meta": 604800,
        "default": 3600,
    }

    def __init__(
        self,
        cache_dir: Path = None,
        l1_maxsize: int = 100,
        l2_maxsize: int = 1000,
        l2_ttl: int = 3600,
    ):
        self._l1: LRUCache = LRUCache(maxsize=l1_maxsize)
        self._l2_ttl: int = l2_ttl
        self._l2: TTLCache = TTLCache(maxsize=l2_maxsize, ttl=l2_ttl)

        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent.parent / ".cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        disk_path = cache_dir / "diskcache"
        disk_path.mkdir(parents=True, exist_ok=True)
        try:
            self._l3: diskcache.Cache = diskcache.Cache(str(disk_path))
        except Exception as e:
            logger.warning(f"DiskCache init failed ({e}), using fallback")
            self._l3 = None

        self._stats = {"l1_hits": 0, "l2_hits": 0, "l3_hits": 0, "misses": 0}

    def _make_key(self, namespace: str, key: str) -> str:
        return f"{namespace}:{key}"

    def _hash_key(self, key: Any) -> str:
        if isinstance(key, str):
            return key
        serialized = json.dumps(key, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def get(self, namespace: str, key: Any) -> Optional[Any]:
        cache_key = self._make_key(namespace, self._hash_key(key))

        if cache_key in self._l1:
            self._stats["l1_hits"] += 1
            return self._l1[cache_key]

        if cache_key in self._l2:
            self._stats["l2_hits"] += 1
            value = self._l2[cache_key]
            self._l1[cache_key] = value
            return value

        if self._l3 is None:
            self._stats["misses"] += 1
            return None
        value = self._l3.get(cache_key)
        if value is not None:
            self._stats["l3_hits"] += 1
            self._l1[cache_key] = value
            self._l2[cache_key] = value
            return value

        self._stats["misses"] += 1
        return None

    def set(
        self,
        namespace: str,
        key: Any,
        value: Any,
        data_type: str = "default",
        ttl: Optional[int] = None,
    ) -> None:
        cache_key = self._make_key(namespace, self._hash_key(key))
        if ttl is None:
            ttl = self.TTL_CONFIG.get(data_type, self.TTL_CONFIG["default"])

        self._l1[cache_key] = value
        if ttl >= self._l2_ttl:
            self._l2[cache_key] = value
        if self._l3 is not None:
            try:
                self._l3.set(cache_key, value, expire=ttl)
            except Exception as e:
                logger.warning(f"L3 cache write failed: {e}")

    def delete(self, namespace: str, key: Any) -> None:
        cache_key = self._make_key(namespace, self._hash_key(key))
        self._l1.pop(cache_key, None)
        self._l2.pop(cache_key, None)
        if self._l3 is not None:
            self._l3.delete(cache_key)

    def get_stats(self) -> dict:
        total = sum(self._stats.values())
        hit_rate = (total - self._stats["misses"]) / total * 100 if total > 0 else 0
        return {
            **self._stats,
            "total_requests": total,
            "hit_rate_percent": round(hit_rate, 2),
            "l1_size": len(self._l1),
            "l2_size": len(self._l2),
            "l3_size": len(self._l3) if self._l3 else 0,
        }

    def close(self) -> None:
        if self._l3:
            self._l3.close()


def cached(namespace: str, data_type: str = "default", key_builder: callable = None):
    """Decorator for caching function results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_mgr = None
            if args and hasattr(args[0], "_cache"):
                cache_mgr = args[0]._cache
            if cache_mgr is None:
                return func(*args, **kwargs)
            if key_builder:
                key = key_builder(*args, **kwargs)
            else:
                key = {"func": func.__name__, "args": args[1:] if args else (), "kwargs": kwargs}
            result = cache_mgr.get(namespace, key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            if result is not None:
                cache_mgr.set(namespace, key, result, data_type)
            return result
        return wrapper
    return decorator


_global_cache: Optional[CacheManager] = None
_cache_lock = __import__("threading").Lock()


def get_cache() -> CacheManager:
    """Get or create the global cache instance."""
    global _global_cache
    if _global_cache is None:
        with _cache_lock:
            if _global_cache is None:
                _global_cache = CacheManager()
    return _global_cache
