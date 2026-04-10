"""
Cache layer that uses Redis when available and falls back to an in-memory
dict-based cache so the app runs without Redis in development.
"""
import asyncio
import json
import logging
import time
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


class _InMemoryBackend:
    """Thread-safe, TTL-aware in-memory cache."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[str]:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return None
            return value

    async def set(self, key: str, value: str, ttl: int) -> None:
        async with self._lock:
            self._store[key] = (value, time.monotonic() + ttl)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        pass


class CacheManager:
    """
    Public cache interface.  Writes go to Redis; on any Redis error the
    manager switches transparently to the in-memory backend.
    """

    def __init__(self) -> None:
        self._redis: Optional[aioredis.Redis] = None
        self._fallback = _InMemoryBackend()
        self._use_redis = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Try to connect to Redis; silently fall back to in-memory."""
        try:
            self._redis = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
            )
            await self._redis.ping()
            self._use_redis = True
            logger.info("Cache: connected to Redis at %s", settings.redis_url)
        except Exception as exc:
            logger.warning(
                "Cache: Redis unavailable (%s) — using in-memory fallback", exc
            )
            self._use_redis = False

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(self, key: str) -> Optional[Any]:
        """Return the cached value or *None* on a miss."""
        try:
            if self._use_redis and self._redis:
                raw = await self._redis.get(key)
                return json.loads(raw) if raw else None
        except Exception as exc:
            logger.warning("Cache: Redis get failed (%s) — switching to fallback", exc)
            self._use_redis = False

        raw = await self._fallback.get(key)
        return json.loads(raw) if raw else None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """Store *value* under *key* with an expiry of *ttl* seconds."""
        serialised = json.dumps(value)
        try:
            if self._use_redis and self._redis:
                await self._redis.set(key, serialised, ex=ttl)
                return
        except Exception as exc:
            logger.warning("Cache: Redis set failed (%s) — switching to fallback", exc)
            self._use_redis = False

        await self._fallback.set(key, serialised, ttl)

    async def ping(self) -> bool:
        """Return True if the active backend is reachable."""
        if self._use_redis and self._redis:
            try:
                await self._redis.ping()
                return True
            except Exception:
                return False
        return True  # in-memory is always reachable

    @property
    def backend_name(self) -> str:
        return "redis" if self._use_redis else "memory"


# Module-level singleton shared across the application
cache = CacheManager()
