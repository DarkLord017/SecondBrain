"""Run: python secondbrain/orchestrator/tests/real_agent_check.py

Live multi-turn check of the agent loop against the real LLM, using
general-knowledge questions that need no tool at all (no TAVILY_API_KEY or
notebook/Supermemory content required — just OPENAI_API_KEY/LLM_MODEL).
Verifies: conversation memory lets a follow-up resolve "that city" from the
prior turn, and the loop doesn't needlessly call tools or blow past
MAX_AGENT_STEPS on ordinary questions.
"""

import asyncio
import sys
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from secondbrain.config import settings  # noqa: E402
from secondbrain.orchestrator import nodes  # noqa: E402
from secondbrain.orchestrator.graph import build_graph  # noqa: E402


async def main() -> None:
    if not settings.openai_api_key or not settings.llm_model:
        print("OPENAI_API_KEY / LLM_MODEL not set in .env -- nothing to run")
        return

    # No Postgres/Supermemory running in this environment -- stub the two
    # external lookups hydrate/warm_up/prime_context make so this can run
    # standalone. The LLM call itself is real.
    async def _no_notebook(notebook_id):
        return None

    async def _no_search(*args, **kwargs):
        return []

    nodes.notebook_store.get_notebook = _no_notebook
    nodes.supermemory_client.search = _no_search

    graph = build_graph(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "real-agent-check"}}

    turns = [
        "What is the capital of France?",
        "What's the population of that city, roughly?",
    ]

    result = None
    for question in turns:
        result = await graph.ainvoke({"user_id": "u1", "notebook_id": "nb1", "question": question}, config)
        print(f"\nQ: {question}")
        print(f"A: {result['final_answer']}")
        print(f"agent_steps: {result['agent_steps']}")
        assert result["final_answer"], "expected a non-empty final answer"
        assert result["agent_steps"] < nodes.MAX_AGENT_STEPS, "hit the step cap on an ordinary question"

    assert "pari" in result["final_answer"].lower(), (
        "expected the follow-up answer to resolve 'that city' as Paris using conversation memory"
    )

    print("\nAll checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
