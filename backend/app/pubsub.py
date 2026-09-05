"""Cross-instance pub/sub for live observation streaming.

Uses Redis Pub/Sub when REDIS_URL is configured so the app scales across
multiple API instances (a WebSocket on instance A receives events published on
instance B). Falls back to an in-process implementation when Redis is absent
(single-instance dev only).

Consumers call `subscribe(session_id)` to get an async iterator of messages and
`publish(session_id, message)` to fan out. The interface is identical for both
backends, so call sites don't change.
"""

import asyncio
import json
import logging
from collections import defaultdict
from collections.abc import AsyncIterator

from .config import settings

log = logging.getLogger("linguacall.pubsub")

_CHANNEL_PREFIX = "obs:"


class _InMemoryPubSub:
    """Single-process fallback. Not for multi-instance production."""

    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)

    async def publish(self, session_id: str, message: dict) -> None:
        for q in list(self._subs.get(session_id, ())):
            if not q.full():
                q.put_nowait(message)

    async def subscription(self, session_id: str) -> AsyncIterator[dict]:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subs[session_id].add(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subs[session_id].discard(q)
            if not self._subs[session_id]:
                self._subs.pop(session_id, None)


class _RedisPubSub:
    """Redis-backed pub/sub — works across many API instances."""

    def __init__(self, url: str) -> None:
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(url, decode_responses=True)

    async def publish(self, session_id: str, message: dict) -> None:
        await self._redis.publish(_CHANNEL_PREFIX + session_id, json.dumps(message))

    async def subscription(self, session_id: str) -> AsyncIterator[dict]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(_CHANNEL_PREFIX + session_id)
        try:
            async for msg in pubsub.listen():
                if msg.get("type") != "message":
                    continue
                try:
                    yield json.loads(msg["data"])
                except (ValueError, TypeError):
                    continue
        finally:
            try:
                await pubsub.unsubscribe(_CHANNEL_PREFIX + session_id)
                await pubsub.close()
            except Exception:
                pass


_backend = None


def get_pubsub():
    global _backend
    if _backend is None:
        if settings.REDIS_URL:
            try:
                _backend = _RedisPubSub(settings.REDIS_URL)
                log.info("pubsub: using Redis at %s", settings.REDIS_URL.split("@")[-1])
            except Exception as e:
                log.warning("pubsub: Redis init failed (%s); falling back to in-memory", e)
                _backend = _InMemoryPubSub()
        else:
            log.info("pubsub: REDIS_URL not set; using in-memory (single-instance only)")
            _backend = _InMemoryPubSub()
    return _backend


def backend_name() -> str:
    return "redis" if settings.REDIS_URL else "in-memory"
