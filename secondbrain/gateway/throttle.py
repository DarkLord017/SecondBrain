import time

import redis.asyncio as redis


class ThrottleExceeded(Exception):
    pass


async def check_rate_limit(r: redis.Redis, user_id: str, notebook_id: str, limit_per_min: int) -> None:
    key = f"throttle:{user_id}:{notebook_id}:{int(time.time() // 60)}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, 60)
    if count > limit_per_min:
        raise ThrottleExceeded("rate limit exceeded")


async def enter_stream_slot(r: redis.Redis, max_concurrent: int) -> None:
    n = await r.incr("streams:concurrent")
    if n > max_concurrent:
        await r.decr("streams:concurrent")
        raise ThrottleExceeded("too many concurrent streams")


async def exit_stream_slot(r: redis.Redis) -> None:
    await r.decr("streams:concurrent")
