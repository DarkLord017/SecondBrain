from secondbrain.orchestrator.registry import register
from secondbrain.orchestrator.state import GraphState, ToolResult
from secondbrain.storage import graph as graph_store


class Skeptic:
    """Finds holes — walks the notebook's Neo4j CONTRADICTS edges (written
    during idea extraction, see ingestion/idea_extraction.py) and surfaces
    them so the writer's clash-check has real signal instead of only
    noticing contradictions it happens to spot itself in the retrieved text.
    """
    name = "skeptic"
    description = "Checks for known contradictions/inconsistencies between ideas in this notebook. Use when the question explicitly asks about contradictions, conflicts, or inconsistencies in the notes."

    async def run(self, state: GraphState, query: str) -> ToolResult:
        try:
            contradictions = await graph_store.get_notebook_contradictions(state["notebook_id"])
            chunks = [
                {
                    "content": (
                        f"CONTRADICTION: {c['a_label']} ({c['a_summary']}) "
                        f"conflicts with {c['b_label']} ({c['b_summary']})"
                    )
                }
                for c in contradictions
            ]
            return ToolResult(tool=self.name, ok=True, chunks=chunks)
        except Exception as e:  # noqa: BLE001 - tool failures must not crash the graph
            return ToolResult(tool=self.name, ok=False, error=str(e))


def register_skeptic() -> None:
    register(Skeptic())
