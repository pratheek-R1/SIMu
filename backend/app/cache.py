"""Redis (Upstash) cache with an in-process fallback.

Cached values are all derived from the dataset seed and are therefore immutable
for the lifetime of a cohort -- aggregate feature counts, the evidence board,
the naive ranking. Per-session state is never cached; it lives in Postgres.
"""

from __future__ import annotations

import json
import time
from typing import Any

from .config import settings

try:  # redis is optional at dev time
    from redis.asyncio import Redis
except ImportError:  # pragma: no cover
    Redis = None  # type: ignore[assignment]

_client: Any = None
_local: dict[str, tuple[float, Any]] = {}


async def get_client():
    global _client
    if _client is None and settings.redis_url and Redis is not None:
        _client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def get(key: str) -> Any | None:
    client = await get_client()
    if client is not None:
        raw = await client.get(key)
        return json.loads(raw) if raw else None

    hit = _local.get(key)
    if not hit:
        return None
    expires_at, value = hit
    if expires_at < time.time():
        _local.pop(key, None)
        return None
    return value


async def set(key: str, value: Any, ttl: int | None = None) -> None:
    ttl = ttl or settings.cache_ttl_seconds
    client = await get_client()
    if client is not None:
        await client.set(key, json.dumps(value), ex=ttl)
        return
    _local[key] = (time.time() + ttl, value)


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
