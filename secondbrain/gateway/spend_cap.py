from datetime import date

import redis.asyncio as redis


class SpendCapExceeded(Exception):
    pass


async def reserve(r: redis.Redis, user_id: str, notebook_id: str, cap_usd: float, cost_cents: int) -> str:
    day_key = f"spend:{user_id}:{notebook_id}:{date.today().isoformat()}"
    new_total = await r.incrby(day_key, cost_cents)
    await r.expire(day_key, 86400)
    if new_total > cap_usd * 100:
        await r.decrby(day_key, cost_cents)
        raise SpendCapExceeded("daily spend cap reached")
    return day_key


async def settle(r: redis.Redis, reservation_key: str, reserved_cents: int, actual_cents: int) -> None:
    delta = actual_cents - reserved_cents
    if delta:
        await r.incrby(reservation_key, delta)
