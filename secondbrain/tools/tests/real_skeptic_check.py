"""Run: python secondbrain/tools/tests/real_skeptic_check.py

Seeds two real contradicting ideas in Neo4j (a CONTRADICTS edge), then
confirms Skeptic actually surfaces it.
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from secondbrain.config import settings  # noqa: E402
from secondbrain.storage import graph as graph_store  # noqa: E402
from secondbrain.storage.neo4j_client import close_driver, init_driver  # noqa: E402
from secondbrain.tools.skeptic import Skeptic  # noqa: E402


async def main() -> None:
    if not settings.neo4j_password:
        print("NEO4J_PASSWORD not set in .env -- nothing to run")
        return

    init_driver()
    try:
        suffix = str(int(time.time()))
        user_id, notebook_id = f"u-{suffix}", f"nb-{suffix}"

        await graph_store.create_user_node(user_id=user_id, email="skeptic-check@example.com")
        await graph_store.create_notebook_node(notebook_id=notebook_id, title="Skeptic check", owner_user_id=user_id)
        await graph_store.merge_ideas(
            notebook_id=notebook_id,
            ideas=[
                {"id": "deadline-march", "label": "Deadline is March 1st", "summary": "From the January note.", "related_to": []},
                {
                    "id": "deadline-april",
                    "label": "Deadline is April 15th",
                    "summary": "From the September note.",
                    "related_to": [],
                    "contradicts": ["deadline-march"],
                },
            ],
        )

        result = await Skeptic().run({"notebook_id": notebook_id, "user_id": user_id}, "when is the deadline?")

        assert result.ok, result.error
        assert result.chunks, "expected Skeptic to find the seeded contradiction"
        content = result.chunks[0]["content"]
        assert content.startswith("CONTRADICTION:")
        assert "March 1st" in content and "April 15th" in content

        print("Skeptic chunk:", content)
        print("\nAll checks passed.")
    finally:
        await close_driver()


if __name__ == "__main__":
    asyncio.run(main())
