from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from secondbrain.chat.events import publish_event
from secondbrain.chat.runner import run_orchestrator_background
from secondbrain.chat.schemas import ChatAck, ChatRequest
from secondbrain.config import settings
from secondbrain.gateway.cache import get_cached
from secondbrain.gateway.firewall import FirewallRejection, check_prompt
from secondbrain.gateway.spend_cap import SpendCapExceeded, reserve
from secondbrain.gateway.throttle import ThrottleExceeded, check_rate_limit
from secondbrain.gateway.tokens import count_tokens, estimate_cost_cents
from secondbrain.storage import runs as runs_store

router = APIRouter(prefix="/notebooks", tags=["chat"])
runs_router = APIRouter(tags=["chat"])


@router.post("/{notebook_id}/chat", response_model=ChatAck, status_code=202)
async def chat(notebook_id: str, req: ChatRequest, request: Request, background_tasks: BackgroundTasks):
    redis = request.app.state.redis

    try:
        question = check_prompt(req.question) 
        await check_rate_limit(redis, req.user_id, notebook_id, settings.throttle_per_min)
    except FirewallRejection as e:
        raise HTTPException(400, str(e))
    except ThrottleExceeded as e:
        raise HTTPException(429, str(e))

    cached = await get_cached(redis, notebook_id, question, settings.cache_similarity_threshold)
    if cached:
        run = await runs_store.create_run(notebook_id=notebook_id, user_id=req.user_id, question=question)
        run_id = str(run["id"])
        await runs_store.update_run_status(run_id, "done", final_answer=cached["answer"])
        await publish_event(run_id, {"type": "final", "data": cached})
        return {"run_id": run_id, "status": "done"}


    input_tokens = count_tokens(question)
    reserved_cents = estimate_cost_cents(
        input_tokens,
        settings.max_response_tokens_estimate,
        settings.price_per_1k_input_tokens,
        settings.price_per_1k_output_tokens,
    )
    try:
        reservation = await reserve(redis, req.user_id, notebook_id, settings.spend_cap_usd, reserved_cents)
    except SpendCapExceeded as e:
        raise HTTPException(402, str(e))

    run = await runs_store.create_run(notebook_id=notebook_id, user_id=req.user_id, question=question)
    run_id = str(run["id"])

    background_tasks.add_task(
        run_orchestrator_background,
        run_id=run_id,
        notebook_id=notebook_id,
        user_id=req.user_id,
        question=question,
        reservation_key=reservation,
        reserved_cents=reserved_cents,
    )

    return {"run_id": run_id, "status": "queued"}


@runs_router.get("/runs/{run_id}")
async def get_run(run_id: str):
    run = await runs_store.get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return run
