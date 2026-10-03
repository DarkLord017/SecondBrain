from secondbrain.orchestrator.registry import register
from secondbrain.orchestrator.state import GraphState, ToolResult
from secondbrain.storage import graph as graph_store


def _idea_to_content(idea: dict) -> str:
    related = [r for r in idea.get("related_labels", []) if r]
    base = f"{idea['label']}: {idea.get('summary', '')}".strip()
    return f"{base} (related to: {', '.join(related)})" if related else base


def _matches_query(idea: dict, query_words: set[str]) -> bool:
    text = f"{idea['label']} {idea.get('summary', '')}".lower()
    return any(w in text for w in query_words)


class Linker:
    """Joins ideas — walks the notebook's Neo4j idea graph to surface how concepts relate to each other.
    """

    name = "linker"
    description = "Shows how concepts/ideas in this notebook connect to each other via the idea graph. Use for questions about relationships between topics, not for retrieving raw note content (use finder for that)."

    async def run(self, state: GraphState, query: str) -> ToolResult:
        try:
            ideas = await graph_store.get_notebook_idea_graph(state["notebook_id"])
            query_words = {w for w in query.lower().split() if len(w) > 3}
            relevant = [i for i in ideas if _matches_query(i, query_words)] or ideas
            chunks = [{"content": _idea_to_content(i), "idea_id": i["id"]} for i in relevant]
            return ToolResult(tool=self.name, ok=True, chunks=chunks)
        except Exception as e:  # noqa: BLE001 - tool failures must not crash the graph
            return ToolResult(tool=self.name, ok=False, error=str(e))


def register_linker() -> None:
    register(Linker())
