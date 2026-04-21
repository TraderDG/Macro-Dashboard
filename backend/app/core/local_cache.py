"""
In-memory drop-in replacement for redis.asyncio.Redis — for local dev without Docker.
Supports: get, set, setex, publish, pubsub (via asyncio.Queue)
"""
import asyncio
import time
from typing import Any, Optional


class LocalPubSub:
    def __init__(self, cache: "LocalCache"):
        self._cache = cache
        self._channels: set[str] = set()
        self._queue: asyncio.Queue = asyncio.Queue()

    async def subscribe(self, *channels: str):
        for ch in channels:
            self._channels.add(ch)
            self._cache._subscribers.setdefault(ch, []).append(self._queue)

    async def unsubscribe(self, *channels: str):
        for ch in channels:
            self._channels.discard(ch)
            subs = self._cache._subscribers.get(ch, [])
            if self._queue in subs:
                subs.remove(self._queue)

    async def get_message(self, ignore_subscribe_messages=True):
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def close(self):
        await self.unsubscribe(*list(self._channels))


class LocalCache:
    """Thread-safe in-memory cache with TTL and pub/sub."""

    def __init__(self):
        self._store: dict[str, tuple[Any, Optional[float]]] = {}
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def _is_expired(self, key: str) -> bool:
        if key not in self._store:
            return True
        _, expiry = self._store[key]
        return expiry is not None and time.time() > expiry

    async def get(self, key: str) -> Optional[str]:
        if self._is_expired(key):
            self._store.pop(key, None)
            return None
        return self._store[key][0]

    async def set(self, key: str, value: Any):
        self._store[key] = (value, None)

    async def setex(self, key: str, ttl: int, value: Any):
        self._store[key] = (value, time.time() + ttl)

    async def delete(self, *keys: str):
        for k in keys:
            self._store.pop(k, None)

    async def publish(self, channel: str, message: str) -> int:
        queues = self._subscribers.get(channel, [])
        for q in queues:
            await q.put({"type": "message", "channel": channel, "data": message})
        return len(queues)

    def pubsub(self) -> LocalPubSub:
        return LocalPubSub(self)

    async def aclose(self):
        pass


# Singleton instance for local mode
_local_cache = LocalCache()


def get_local_cache() -> LocalCache:
    return _local_cache
