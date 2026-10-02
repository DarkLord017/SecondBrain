import json

from secondbrain.storage.redis_client import get_redis

LOG_KEY = "run:{run_id}:log"
CHANNEL = "run:{run_id}:events"
LOG_TTL_SECONDS = 3600
LOG_MAX_LEN = 500


async def publish_event(run_id: str, event: dict) -> None:
    r = get_redis()
    payload = json.dumps(event)
    log_key = LOG_KEY.format(run_id=run_id)
    await r.rpush(log_key, payload)
    await r.ltrim(log_key, -LOG_MAX_LEN, -1)
    await r.expire(log_key, LOG_TTL_SECONDS)
    await r.publish(CHANNEL.format(run_id=run_id), payload)


async def get_log(run_id: str) -> list[dict]:
    r = get_redis()
    items = await r.lrange(LOG_KEY.format(run_id=run_id), 0, -1)
    return [json.loads(i) for i in items]
