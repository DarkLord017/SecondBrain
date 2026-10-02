from secondbrain.integrations import supermemory_client
from secondbrain.orchestrator.registry import register
from secondbrain.orchestrator.state import GraphState, ToolResult


class Finder:
    name = "finder"

    async def run(self, state: GraphState, query: str) -> ToolResult:
        try:
            results = await supermemory_client.search(
                query=query,
                container_tags=[f"user:{state['user_id']}", f"notebook:{state['notebook_id']}"],
            )
            return ToolResult(tool=self.name, ok=True, chunks=results)
        except Exception as e:  # noqa: BLE001 - tool failures must not crash the graph
            return ToolResult(tool=self.name, ok=False, error=str(e))


def register_finder() -> None:
    register(Finder())
