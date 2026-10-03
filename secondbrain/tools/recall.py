from secondbrain.integrations import supermemory_client
from secondbrain.orchestrator.registry import register
from secondbrain.orchestrator.state import GraphState, ToolResult


class Recall:
    """Pulls facts Supermemory has learned about the user (the user profile
    memory written on signup, and anything else landed under the `user:<id>`
    tag) — scoped by user, not notebook, unlike Finder.
    """

    name = "recall"
    description = (
        "Recalls facts previously learned about the user as a person — their stated "
        "preferences, background, and prior statements about themselves (not notebook "
        "content, use finder for that). Use it to gauge the user's familiarity with a "
        "topic and their preferred explanation style, so the answer can be pitched at "
        "the right level."
    )

    async def run(self, state: GraphState, query: str) -> ToolResult:
        try:
            results = await supermemory_client.search(
                query=query,
                container_tags=[f"user:{state['user_id']}"],
            )
            return ToolResult(tool=self.name, ok=True, chunks=results)
        except Exception as e:  # noqa: BLE001 - tool failures must not crash the graph
            return ToolResult(tool=self.name, ok=False, error=str(e))


def register_recall() -> None:
    register(Recall())
