from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from secondbrain.chat.events import CHANNEL, get_log
from secondbrain.config import settings
from secondbrain.gateway.throttle import ThrottleExceeded, enter_stream_slot, exit_stream_slot
from secondbrain.storage import runs as runs_store
from secondbrain.storage.redis_client import get_redis

router = APIRouter()


@router.websocket("/ws/runs/{run_id}")
async def ws_run(ws: WebSocket, run_id: str):
    await ws.accept()

    run = await runs_store.get_run(run_id)
    if not run:
        await ws.send_json({"type": "error", "data": "run not found"})
        await ws.close()
        return

    log = await get_log(run_id)
    for event in log:
        await ws.send_json(event)

    already_final = any(e["type"] in ("final", "error") for e in log)
    if already_final or run["status"] in ("done", "error"):
        if not already_final and run["status"] == "done":
            await ws.send_json(
                {"type": "final", "data": {"answer": run["final_answer"], "citations": [], "citation_flags": []}}
            )
        elif not already_final and run["status"] == "error":
            await ws.send_json({"type": "error", "data": run["error"]})
        await ws.close()
        return

    redis = get_redis()
    user_id = str(run["user_id"])
    try:
        await enter_stream_slot(redis, user_id, settings.max_concurrent_streams)
    except ThrottleExceeded:
        await ws.send_json({"type": "error", "data": "too many concurrent streams for this user"})
        await ws.close()
        return

    pubsub = redis.pubsub()
    channel = CHANNEL.format(run_id=run_id)
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            await ws.send_text(message["data"])
            if '"type": "final"' in message["data"] or '"type": "error"' in message["data"]:
                break
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await exit_stream_slot(redis, user_id)
        try:
            await ws.close()
        except RuntimeError:
            pass
