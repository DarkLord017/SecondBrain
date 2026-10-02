from datetime import date

import redis.asyncio as redis


class UploadQuotaExceeded(Exception):
    pass


async def reserve_upload_quota(r: redis.Redis, user_id: str, notebook_id: str, size_bytes: int, quota_bytes_per_day: int) -> str:
    day_key = f"uploadquota:{user_id}:{notebook_id}:{date.today().isoformat()}"
    new_total = await r.incrby(day_key, size_bytes)
    await r.expire(day_key, 86400)
    if new_total > quota_bytes_per_day:
        await r.decrby(day_key, size_bytes)
        raise UploadQuotaExceeded("daily upload quota reached")
    return day_key


async def settle_upload_quota(r: redis.Redis, reservation_key: str, size_bytes: int, success: bool) -> None:
    if not success:
        await r.decrby(reservation_key, size_bytes)
