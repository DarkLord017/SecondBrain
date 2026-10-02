import redis.asyncio as redis

from secondbrain.config import settings

_client: redis.Redis | None = None


def init_redis() -> redis.Redis:
    global _client
    _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def get_redis() -> redis.Redis:
    if _client is None:
        raise RuntimeError("redis client not initialized — call init_redis() during app startup")
    return _client
