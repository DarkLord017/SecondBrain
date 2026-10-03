from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from secondbrain.orchestrator.state import GraphState, ToolResult


class ToolAgent(Protocol):
    name: str
    description: str

    async def run(self, state: "GraphState", query: str) -> "ToolResult": ...


TOOL_REGISTRY: dict[str, ToolAgent] = {}


def register(agent: ToolAgent) -> None:
    TOOL_REGISTRY[agent.name] = agent
