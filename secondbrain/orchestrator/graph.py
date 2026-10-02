from langgraph.graph import END, StateGraph

from secondbrain.orchestrator import nodes
from secondbrain.orchestrator.registry import TOOL_REGISTRY
from secondbrain.orchestrator.state import GraphState


def build_tool_node(name: str):
    agent = TOOL_REGISTRY[name]

    async def _node(state: GraphState) -> dict:
        step = next(
            s for s in state["plan"] if s["tool"] == name and s["wave"] == state["current_wave"]
        )
        result = await agent.run(state, step["query"])
        return {"tool_results": {name: result}}

    return _node


def build_graph(checkpointer=None):
    g = StateGraph(GraphState)
    g.add_node("hydrate", nodes.hydrate)
    g.add_node("warm_up", nodes.warm_up)
    g.add_node("planner", nodes.planner)
    g.add_node("router", nodes.router)
    g.add_node("writer", nodes.writer)

    tool_names = list(TOOL_REGISTRY.keys())
    for name in tool_names:
        g.add_node(f"tool_{name}", build_tool_node(name))
        g.add_edge(f"tool_{name}", "router")

    tool_node_map = {f"tool_{n}": f"tool_{n}" for n in tool_names} | {"router": "router"}

    g.set_entry_point("hydrate")
    g.add_edge("hydrate", "warm_up")
    g.add_conditional_edges(
        "warm_up", nodes.route_after_warmup, {"planner": "planner", "writer": "writer"}
    )
    g.add_conditional_edges("planner", nodes.route_after_planner, tool_node_map)
    g.add_conditional_edges(
        "router", nodes.route_after_router, tool_node_map | {"writer": "writer"}
    )
    g.add_edge("writer", END)

    return g.compile(checkpointer=checkpointer)
