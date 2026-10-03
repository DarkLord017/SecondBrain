from langgraph.graph import END, StateGraph

from secondbrain.orchestrator import nodes
from secondbrain.orchestrator.state import GraphState


def build_graph(checkpointer=None):
    g = StateGraph(GraphState)
    g.add_node("hydrate", nodes.hydrate)
    g.add_node("warm_up", nodes.warm_up)
    g.add_node("prime_context", nodes.prime_context)
    g.add_node("agent", nodes.agent)
    g.add_node("tools", nodes.tools)
    g.add_node("finalize", nodes.finalize)

    g.set_entry_point("hydrate")
    g.add_edge("hydrate", "warm_up")
    g.add_edge("warm_up", "prime_context")
    g.add_edge("prime_context", "agent")
    g.add_conditional_edges("agent", nodes.route_after_agent, {"tools": "tools", "finalize": "finalize"})
    g.add_edge("tools", "agent")
    g.add_edge("finalize", END)

    return g.compile(checkpointer=checkpointer)
