"""Rate limiting distribuído com janela fixa atômica no Redis."""
from __future__ import annotations

import hashlib
import hmac

from app.config import SECRET_KEY
from app.redis_client import redis_async


_INCREMENT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""


def opaque_key(value: str) -> str:
    return hmac.new(
        SECRET_KEY.encode("utf-8"),
        value.casefold().strip().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def consume(key: str, limit: int, window_seconds: int) -> tuple[bool, int, int]:
    """Retorna permitido, tentativas restantes e segundos até liberar."""
    current, ttl = await redis_async().eval(
        _INCREMENT_SCRIPT,
        1,
        key,
        window_seconds,
    )
    current = int(current)
    ttl = max(int(ttl), 1)
    return current <= limit, max(limit - current, 0), ttl


async def inspect_limit(key: str, limit: int) -> tuple[bool, int]:
    """Consulta um limite sem registrar uma nova tentativa."""
    async with redis_async().pipeline(transaction=False) as pipeline:
        pipeline.get(key)
        pipeline.ttl(key)
        current_raw, ttl_raw = await pipeline.execute()
    current = int(current_raw or 0)
    ttl = max(int(ttl_raw or 0), 1)
    return current < limit, ttl


async def clear(key: str) -> None:
    await redis_async().delete(key)
