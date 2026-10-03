import asyncio

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool

from secondbrain.config import settings
from secondbrain.integrations import supermemory_client
from secondbrain.integrations.llm import get_chat_model
from secondbrain.orchestrator.fact_check import check_citations
from secondbrain.orchestrator.registry import TOOL_REGISTRY
from secondbrain.orchestrator.state import GraphState, ToolResult
from secondbrain.storage import notebooks as notebook_store

MAX_AGENT_STEPS = 4

SYSTEM_PROMPT = (
    "You are a notebook Q&A assistant. Use the available tools to gather information, "
    "then answer the user's question. Cite sources inline as [n] referencing the order "
    "tool results appeared. If sources conflict, flag the conflict explicitly rather than "
    "silently picking one. Any tool result starting with 'CONTRADICTION:' is a confirmed "
    "conflict already detected in the notebook's idea graph (not just something you "
    "noticed) — always surface it if relevant. Only call tools you actually need; never "
    "call the same tool twice with near-duplicate queries."
)

# Which tool_results entries, if already populated by warm_up/prime_context
# before the agent's first turn, get folded into the system prompt as
# background context instead of the agent having to call them itself.
PRIMED_TOOLS = ("recall", "finder")


def _chunks_to_text(chunks: list[dict]) -> str:
    return "\n\n".join(c.get("content") or c.get("memory") or c.get("chunk") or "" for c in chunks)


async def hydrate(state: GraphState) -> dict:
    nb = await notebook_store.get_notebook(state["notebook_id"])
    return {
        "notebook_context": dict(nb) if nb else {},
        "tool_results": {},
        "agent_steps": 0,
        "citation_flags": [],
        "messages": [HumanMessage(content=state["question"])],
    }


async def warm_up(state: GraphState) -> dict:
    """Proactively checks Recall for a high-confidence fact about the user
    before the agent's first turn. Just populates tool_results — the agent
    node folds this into its system prompt as background context (see
    _primed_context_block), it does NOT fabricate a fake tool-call message.
    """
    try:
        results = await supermemory_client.search(
            query=state["question"], container_tags=[f"user:{state['user_id']}"], limit=1
        )
    except Exception:  # noqa: BLE001 - warm-up is a shortcut, never a hard dependency
        return {}

    if not results or results[0].get("similarity", 0) < settings.warmup_similarity_threshold:
        return {}

    return {
        "tool_results": {
            **state["tool_results"],
            "recall": ToolResult(tool="recall", ok=True, chunks=[results[0]]),
        }
    }


async def prime_context(state: GraphState) -> dict:
    """Same idea as warm_up, but a quick Finder search over notebook
    content, so the agent's first turn isn't deciding what to call while
    blind to what's actually in the notebook. The agent can still call
    Finder itself for more/different results — the system prompt tells it
    this is a starting point, not the full answer.
    """
    try:
        results = await supermemory_client.search(
            query=state["question"], container_tags=[f"notebook:{state['notebook_id']}"], limit=3
        )
    except Exception:  # noqa: BLE001 - priming is a shortcut, never a hard dependency
        return {}

    if not results:
        return {}

    return {
        "tool_results": {
            **state["tool_results"],
            "finder": ToolResult(tool="finder", ok=True, chunks=results),
        }
    }


def _primed_context_block(state: GraphState) -> str:
    results = state.get("tool_results", {})
    sections = [
        f"Already retrieved from {name}:\n{_chunks_to_text(result.chunks)}"
        for name in PRIMED_TOOLS
        if (result := results.get(name)) and result.ok and result.chunks
    ]
    if not sections:
        return ""
    return (
        "\n\nBackground context retrieved before you started (you don't need to call these "
        "tools again unless you need more or different information):\n\n" + "\n\n".join(sections)
    )


def _notebook_context_line(state: GraphState) -> str:
    title = state.get("notebook_context", {}).get("title")
    return f"\n\nYou are answering questions about the notebook titled {title!r}." if title else ""


def _tool_specs() -> list[StructuredTool]:
    async def _stub(query: str) -> str:
        raise NotImplementedError("tool execution happens in the tools node, not via this stub")

    return [
        StructuredTool.from_function(coroutine=_stub, name=name, description=agent_obj.description)
        for name, agent_obj in TOOL_REGISTRY.items()
    ]


async def agent(state: GraphState) -> dict:
    model = get_chat_model().bind_tools(_tool_specs())
    system = SystemMessage(
        content=SYSTEM_PROMPT + _notebook_context_line(state) + _primed_context_block(state)
    )
    resp = await model.ainvoke([system, *state["messages"]])
    return {"messages": [resp], "agent_steps": state["agent_steps"] + 1}


def route_after_agent(state: GraphState) -> str:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None) and state["agent_steps"] < MAX_AGENT_STEPS:
        return "tools"
    return "finalize"


async def tools(state: GraphState) -> dict:
    last = state["messages"][-1]

    async def _run_one(call: dict):
        agent_obj = TOOL_REGISTRY.get(call["name"])
        if agent_obj is None:
            return call, ToolResult(tool=call["name"], ok=False, error=f"unknown tool: {call['name']}")

        async def _coro(query: str) -> ToolResult:
            return await agent_obj.run(state, query)

        wrapped = StructuredTool.from_function(coroutine=_coro, name=call["name"], description=agent_obj.description)
        result: ToolResult = await wrapped.ainvoke({"query": call["args"].get("query", "")})
        return call, result

    ran = await asyncio.gather(*(_run_one(c) for c in last.tool_calls))

    tool_messages = []
    updated_results = dict(state["tool_results"])
    for call, result in ran:
        updated_results[call["name"]] = result
        content = _chunks_to_text(result.chunks) if result.ok else f"error: {result.error}"
        tool_messages.append(ToolMessage(content=content or "(no results)", tool_call_id=call["id"], name=call["name"]))

    return {"messages": tool_messages, "tool_results": updated_results}


async def finalize(state: GraphState) -> dict:
    chunks = [
        {"tool": tool, **c}
        for tool, result in state["tool_results"].items()
        for c in (result.chunks if result.ok else [])
    ]
    last = state["messages"][-1]
    final_answer = last.content if isinstance(last, AIMessage) else ""
    if not final_answer and state["agent_steps"] >= MAX_AGENT_STEPS:
        final_answer = "I wasn't able to finish gathering information in time — please try rephrasing your question."
    return {"final_answer": final_answer, "citations": chunks}


async def fact_check(state: GraphState) -> dict:
    flags = await check_citations(state.get("final_answer") or "", state.get("citations") or [])
    return {"citation_flags": flags}
