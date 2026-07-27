"""Clientes Redis compartilhados por rate limit e revogação."""
from __future__ import annotations

from functools import lru_cache

import redis
import redis.asyncio as async_redis

from app.config import REDIS_URL


@lru_cache(maxsize=1)
def redis_sync() -> redis.Redis:
    return redis.Redis.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
        health_check_interval=30,
    )

@lru_cache(maxsize=1)
def redis_async() -> async_redis.Redis:
    return async_redis.Redis.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
        health_check_interval=30,
    )
