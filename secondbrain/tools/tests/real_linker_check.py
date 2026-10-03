"""Run: python secondbrain/tools/tests/real_linker_check.py

Seeds a tiny real idea graph in Neo4j (two related ideas), then confirms
Linker actually walks the RELATES_TO edge, not just returning a flat list.
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from secondbrain.config import settings  # noqa: E402
from secondbrain.storage import graph as graph_store  # noqa: E402
from secondbrain.storage.neo4j_client import close_driver, init_driver  # noqa: E402
from secondbrain.tools.linker import Linker  # noqa: E402


async def main() -> None:
    if not settings.neo4j_password:
        print("NEO4J_PASSWORD not set in .env -- nothing to run")
        return

    init_driver()
    try:
        suffix = str(int(time.time()))
        user_id, notebook_id = f"u-{suffix}", f"nb-{suffix}"

        await graph_store.create_user_node(user_id=user_id, email="linker-check@example.com")
        await graph_store.create_notebook_node(notebook_id=notebook_id, title="Linker check", owner_user_id=user_id)
        await graph_store.merge_ideas(
            notebook_id=notebook_id,
            ideas=[
                {"id": "black-holes", "label": "Black Holes", "summary": "Regions of extreme gravity.", "related_to": ["event-horizon"]},
                {"id": "event-horizon", "label": "Event Horizon", "summary": "The boundary of no return.", "related_to": []},
            ],
        )

        result = await Linker().run({"notebook_id": notebook_id, "user_id": user_id}, "black holes")

        assert result.ok, result.error
        assert result.chunks, "expected Linker to find the seeded ideas"
        content = result.chunks[0]["content"]
        assert "Black Holes" in content
        assert "Event Horizon" in content, f"expected the RELATES_TO walk to surface Event Horizon, got: {content!r}"

        print("Linker chunk:", content)
        print("\nAll checks passed.")
    finally:
        await close_driver()


if __name__ == "__main__":
    asyncio.run(main())
