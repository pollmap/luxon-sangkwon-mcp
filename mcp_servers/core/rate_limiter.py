"""
Rate Limiter for MCP servers using Token Bucket algorithm.
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""
    capacity: float
    rate: float
    tokens: float = field(init=False)
    last_update: float = field(init=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def __post_init__(self):
        self.tokens = self.capacity
        self.last_update = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now

    def consume(self, tokens: int = 1) -> bool:
        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def wait_time(self, tokens: int = 1) -> float:
        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                return 0.0
            return (tokens - self.tokens) / self.rate

    def available(self) -> float:
        with self._lock:
            self._refill()
            return self.tokens


DEFAULT_QUOTAS: Dict[str, int] = {
    "kakao": 300,
    "data_go_kr": 100,
    "sangkwon_db": 1000,
    "default": 60,
}


class RateLimiter:
    """Rate limiter managing multiple service quotas."""

    def __init__(self, quotas: Dict[str, int] = None):
        self._quotas = quotas or DEFAULT_QUOTAS.copy()
        self._buckets: Dict[str, TokenBucket] = {}
        self._stats: Dict[str, Dict[str, int]] = {}

    def _get_bucket(self, service: str) -> TokenBucket:
        if service not in self._buckets:
            rpm = self._quotas.get(service, self._quotas["default"])
            self._buckets[service] = TokenBucket(capacity=rpm, rate=rpm / 60.0)
            self._stats[service] = {"acquired": 0, "waited": 0, "rejected": 0}
        return self._buckets[service]

    def acquire(self, service: str, tokens: int = 1, wait: bool = True) -> bool:
        bucket = self._get_bucket(service)
        if bucket.consume(tokens):
            self._stats[service]["acquired"] += tokens
            return True
        if not wait:
            self._stats[service]["rejected"] += tokens
            return False
        while True:
            wait_time = bucket.wait_time(tokens)
            if wait_time > 0:
                self._stats[service]["waited"] += 1
                time.sleep(wait_time)
            if bucket.consume(tokens):
                self._stats[service]["acquired"] += tokens
                return True

    async def acquire_async(self, service: str, tokens: int = 1, wait: bool = True) -> bool:
        bucket = self._get_bucket(service)
        if bucket.consume(tokens):
            self._stats[service]["acquired"] += tokens
            return True
        if not wait:
            self._stats[service]["rejected"] += tokens
            return False
        while True:
            wait_time = bucket.wait_time(tokens)
            if wait_time > 0:
                self._stats[service]["waited"] += 1
                await asyncio.sleep(wait_time)
            if bucket.consume(tokens):
                self._stats[service]["acquired"] += tokens
                return True

    def get_stats(self) -> Dict[str, Dict[str, int]]:
        return {
            service: {**stats, "available": round(self._get_bucket(service).available(), 1)}
            for service, stats in self._stats.items()
        }


_global_limiter: Optional[RateLimiter] = None
_limiter_lock = Lock()


def get_limiter() -> RateLimiter:
    """Get or create the global rate limiter instance."""
    global _global_limiter
    if _global_limiter is None:
        with _limiter_lock:
            if _global_limiter is None:
                _global_limiter = RateLimiter()
    return _global_limiter
