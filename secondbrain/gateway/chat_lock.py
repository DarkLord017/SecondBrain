import asyncio

import redis.asyncio as redis

# Safety ceiling: if a worker crashes mid-run without releasing the lock,
# don't block that notebook+user's chat forever — just bound it.
LOCK_TTL_SECONDS = 600
POLL_INTERVAL_SECONDS = 0.5


def _lock_key(thread_id: str) -> str:
    return f"chatlock:{thread_id}"


async def acquire_run_lock(r: redis.Redis, thread_id: str) -> None:
    key = _lock_key(thread_id)
    while not await r.set(key, "1", nx=True, ex=LOCK_TTL_SECONDS):
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def release_run_lock(r: redis.Redis, thread_id: str) -> None:
    await r.delete(_lock_key(thread_id))
