"""
Redis Cache Layer
==================

Provides TTL-based caching for hot data (latest signals, stats).
Falls back gracefully to direct DB queries if Redis is unavailable.
"""
import json
import os
import time
from typing import Optional, Any, Callable
from datetime import datetime, timezone

# Use sync redis client (works with FastAPI sync endpoints)
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Cache TTLs (seconds)
CACHE_SIGNALS_TTL = int(os.getenv("CACHE_SIGNALS_TTL", "30"))
CACHE_STATS_TTL = int(os.getenv("CACHE_STATS_TTL", "60"))

# With Redis down, retry the connection at most this often (per process) so
# an outage heals without a restart but requests don't pay a connect attempt
# on every call.
RECONNECT_COOLDOWN_SECONDS = 30.0


class RedisCache:
    """
    Sync Redis cache wrapper with graceful fallback.

    Usage:
        cache = RedisCache()
        data = cache.get("signals:latest:page1")
        if data is None:
            data = compute_signals()
            cache.set("signals:latest:page1", data, ttl=30)
    """

    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._available = False
        self._last_connect_attempt = 0.0
        self._connect()

    def _connect(self):
        """Try to connect to Redis. If it fails, cache is disabled."""
        self._last_connect_attempt = time.monotonic()
        try:
            self._client = redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            self._client.ping()
            self._available = True
            print("Redis cache connected")
        except Exception as e:
            self._available = False
            self._client = None
            print(f"Redis cache unavailable (falling back to DB): {e}")

    @property
    def available(self) -> bool:
        """Redis reachability; with a cooldown, retries a dead connection so
        an outage heals without a process restart."""
        if not self._available and (
            time.monotonic() - self._last_connect_attempt >= RECONNECT_COOLDOWN_SECONDS
        ):
            self._connect()
        return self._available

    def get(self, key: str) -> Optional[Any]:
        """Get a cached value. Returns None on miss or if Redis is down."""
        if not self.available:
            return None
        try:
            raw = self._client.get(key)
            if raw is not None:
                return json.loads(raw)
            return None
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: int = 30) -> bool:
        """Set a cached value with TTL. Returns False if Redis is down."""
        if not self.available:
            return False
        try:
            self._client.setex(key, ttl, json.dumps(value, default=str))
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        """Delete a cached key."""
        if not self.available:
            return False
        try:
            self._client.delete(key)
            return True
        except Exception:
            return False

    def invalidate_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern (e.g., 'signals:*')."""
        if not self.available:
            return 0
        try:
            keys = list(self._client.scan_iter(match=pattern, count=100))
            if keys:
                return self._client.delete(*keys)
            return 0
        except Exception:
            return 0

    def get_or_compute(self, key: str, compute_fn: Callable, ttl: int = 30) -> Any:
        """
        Cache-aside pattern: return cached value or compute + cache it.

        Args:
            key: Cache key
            compute_fn: Zero-arg callable that returns the data
            ttl: Cache TTL in seconds
        """
        cached = self.get(key)
        if cached is not None:
            return cached

        result = compute_fn()
        self.set(key, result, ttl)
        return result

    def rate_limit(self, key: str, max_attempts: int, window_seconds: int) -> bool:
        """
        Fixed-window rate limit. Returns True when the attempt is ALLOWED.

        Fail-open: with Redis unavailable or erroring, everything is allowed —
        an auth endpoint must not lock users out because the limiter's
        backend is down.
        """
        if not self.available or self._client is None:
            return True
        try:
            count = self._client.incr(key)
            if count == 1:
                self._client.expire(key, window_seconds)
            return int(count) <= max_attempts
        except Exception:
            return True

    def health_check(self) -> dict:
        """Return Redis health status."""
        if not self.available:
            return {"status": "unavailable", "message": "Redis not connected"}
        try:
            self._client.ping()
            info = self._client.info("memory")
            return {
                "status": "ok",
                "used_memory_human": info.get("used_memory_human", "unknown"),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Singleton instance
cache = RedisCache()
