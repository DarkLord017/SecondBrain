from secondbrain.chat.events import publish_event
from secondbrain.config import settings
from secondbrain.gateway.cache import set_cached
from secondbrain.gateway.firewall import redact_pii
from secondbrain.gateway.spend_cap import settle
from secondbrain.gateway.tokens import count_tokens, estimate_cost_cents
from secondbrain.orchestrator.checkpointer import get_checkpointer
from secondbrain.orchestrator.graph import build_graph
from secondbrain.storage import ledger as ledger_store
from secondbrain.storage import runs as runs_store
from secondbrain.storage.redis_client import get_redis


async def run_orchestrator_background(
    run_id: str,
    notebook_id: str,
    user_id: str,
    question: str,
    reservation_key: str,
    reserved_cents: int,
) -> None:
    await runs_store.update_run_status(run_id, "running")
    redis = get_redis()

    graph = build_graph(checkpointer=get_checkpointer())
    initial_state = {
        "user_id": user_id,
        "notebook_id": notebook_id,
        "question": question,
        "citations": [],
    }
    # Stable per (notebook, user) thread, NOT per run_id — this is what gives
    # the conversation cross-turn memory via the checkpointer. run_id stays
    # separate, for ledger/status/WS-pubsub correlation of this one request.
    config = {"configurable": {"thread_id": f"{notebook_id}:{user_id}"}}

    final_text_parts: list[str] = []
    final_citations: list[dict] = []

    try:
        async for event in graph.astream_events(initial_state, config, version="v2"):
            if (
                event["event"] == "on_chat_model_stream"
                and event.get("metadata", {}).get("langgraph_node") == "agent"
            ):
                token = event["data"]["chunk"].content
                if token:
                    final_text_parts.append(token)
                    await publish_event(run_id, {"type": "token", "data": token})
            if event["event"] == "on_chain_end" and event["name"] == "finalize":
                final_citations = (event["data"]["output"] or {}).get("citations", [])

        final_answer = redact_pii("".join(final_text_parts))
        await runs_store.update_run_status(run_id, "done", final_answer=final_answer)

        input_tokens = count_tokens(question)
        output_tokens = count_tokens(final_answer)
        actual_cents = estimate_cost_cents(
            input_tokens, output_tokens, settings.price_per_1k_input_tokens, settings.price_per_1k_output_tokens
        )
        await settle(redis, reservation_key, reserved_cents, actual_cents)
        await ledger_store.record(
            run_id=run_id,
            notebook_id=notebook_id,
            user_id=user_id,
            cost_cents=actual_cents,
            tokens_in=input_tokens,
            tokens_out=output_tokens,
        )
        await set_cached(
            redis, notebook_id, question, final_answer, final_citations, run_id, settings.cache_ttl_seconds
        )

        await publish_event(run_id, {"type": "final", "data": {"answer": final_answer, "citations": final_citations}})
    except Exception as e:  # noqa: BLE001 - must always resolve the run, never hang a WS client
        await runs_store.update_run_status(run_id, "error", error=str(e))
        await settle(redis, reservation_key, reserved_cents, 0)
        await publish_event(run_id, {"type": "error", "data": str(e)})
