from secondbrain.integrations import tavily_client
from secondbrain.orchestrator.registry import register
from secondbrain.orchestrator.state import GraphState, ToolResult

MAX_RESULTS = 3  

class Scout:
    name = "scout"
    description = (
        "Searches the public web for information outside the user's notes — current "
        "events, general knowledge, or anything missing from the notebook. Never use "
        "for content that should come from the user's own notes (use finder for that)."
    )

    async def run(self, state: GraphState, query: str) -> ToolResult:
        try:
            results = await tavily_client.search(query=query, max_results=MAX_RESULTS)
            return ToolResult(tool=self.name, ok=True, chunks=results)
        except Exception as e:  # noqa: BLE001 - tool failures must not crash the graph
            return ToolResult(tool=self.name, ok=False, error=str(e))


def register_scout() -> None:
    register(Scout())
