import json

from secondbrain.integrations.llm import get_chat_model
from secondbrain.orchestrator.registry import TOOL_REGISTRY
from secondbrain.orchestrator.state import GraphState, PlanStep
from secondbrain.storage import notebooks as notebook_store

MAX_PLAN_STEPS = 5
MAX_RETRIES = 2


async def hydrate(state: GraphState) -> dict:
    nb = await notebook_store.get_notebook(state["notebook_id"])
    return {"notebook_context": dict(nb) if nb else {}}


async def warm_up(state: GraphState) -> dict:
    # No-op placeholder: once a Recall tool-agent exists, do a cheap
    # Supermemory profile lookup here for an instant high-confidence answer.
    # Kept as a real graph node now so the control-flow shape (hydrate ->
    # warm_up -> planner, and the router's loop-back) doesn't need
    # restructuring when that's added.
    return {"warmup_answer": None}


def route_after_warmup(state: GraphState) -> str:
    return "writer" if state["warmup_answer"] else "planner"


async def planner(state: GraphState) -> dict:
    model = get_chat_model()
    available_tools = list(TOOL_REGISTRY.keys())
    prompt = (
        "You are a planner for a notebook Q&A assistant. "
        f"Available tools: {available_tools}. "
        f"Question: {state['question']!r}. "
        f"Produce at most {MAX_PLAN_STEPS} steps as a JSON array ONLY, no prose: "
        '[{"tool": "<one of available_tools>", "query": "<search text>", "wave": <int starting at 0>}]. '
        "Steps with the same wave number run in parallel."
    )
    resp = await model.ainvoke(prompt)
    try:
        raw_steps = json.loads(resp.content)
    except (json.JSONDecodeError, TypeError):
        raw_steps = []

    steps: list[PlanStep] = [s for s in raw_steps[:MAX_PLAN_STEPS] if s.get("tool") in TOOL_REGISTRY]
    if not steps and TOOL_REGISTRY:
        default_tool = "finder" if "finder" in TOOL_REGISTRY else next(iter(TOOL_REGISTRY))
        steps = [{"tool": default_tool, "query": state["question"], "wave": 0}]

    return {"plan": steps, "current_wave": 0, "tool_results": {}, "retries": 0}


def _wave_node_names(state: GraphState, wave: int) -> list[str]:
    names = [f"tool_{s['tool']}" for s in state["plan"] if s["wave"] == wave]
    return names or ["router"]


def route_after_planner(state: GraphState) -> list[str]:
    return _wave_node_names(state, state["current_wave"])


async def router(state: GraphState) -> dict:
    wave_steps = [s for s in state["plan"] if s["wave"] == state["current_wave"]]
    wave_results = [state["tool_results"].get(s["tool"]) for s in wave_steps]
    any_failed = any(r is None or not r.ok for r in wave_results)

    if any_failed and state["retries"] < MAX_RETRIES:
        return {"retries": state["retries"] + 1, "route_decision": "retry"}

    next_wave = state["current_wave"] + 1
    has_more_waves = any(s["wave"] == next_wave for s in state["plan"])
    if has_more_waves:
        return {"current_wave": next_wave, "route_decision": "next_wave"}

    return {"route_decision": "finish"}


def route_after_router(state: GraphState):
    decision = state["route_decision"]
    if decision in ("retry", "next_wave"):
        return _wave_node_names(state, state["current_wave"])
    return "writer"


async def writer(state: GraphState) -> dict:
    model = get_chat_model()
    chunks = [
        {"tool": tool, **c}
        for tool, result in state["tool_results"].items()
        for c in (result.chunks if result.ok else [])
    ]
    context_text = "\n\n".join(
        f"[{i}] (source={c['tool']}) {c.get('content') or c.get('memory') or c.get('chunk')}"
        for i, c in enumerate(chunks)
    )
    prompt = (
        "Answer the question using only the numbered sources below; cite sources inline as [n]. "
        "If sources conflict, flag the conflict explicitly rather than silently picking one.\n\n"
        f"Question: {state['question']}\n\nSources:\n{context_text or '(none found)'}"
    )
    resp = await model.ainvoke(prompt)
    return {"final_answer": resp.content, "citations": chunks}
