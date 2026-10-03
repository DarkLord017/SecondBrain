from typing import Protocol

from secondbrain.orchestrator.state import GraphState, ToolResult


class ToolAgent(Protocol):
    name: str
    description: str

    async def run(self, state: GraphState, query: str) -> ToolResult: ...
