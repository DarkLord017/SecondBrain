"""Run: python secondbrain/tools/tests/real_recall_check.py"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from secondbrain.config import settings  # noqa: E402
from secondbrain.integrations.supermemory_client import write_memory  # noqa: E402
from secondbrain.tools.recall import Recall  # noqa: E402


async def main() -> None:
    if not settings.supermemory_api_key:
        print("SUPERMEMORY_API_KEY not set in .env -- nothing to run")
        return

    user_id = f"recall-check-{int(time.time())}"
    content = "This user prefers concise, bullet-pointed answers over long paragraphs."

    await write_memory(content=content, container_tag=f"user:{user_id}", metadata={"probe": True})
    print("seeded real user fact, waiting for Supermemory to index it...")
    await asyncio.sleep(8)

    result = await Recall().run({"notebook_id": "n/a", "user_id": user_id}, "what does the user prefer?")

    assert result.ok, result.error
    assert result.chunks, "expected Recall to find the seeded fact"
    found = any("bullet-pointed" in (c.get("content") or c.get("memory") or "") for c in result.chunks)
    assert found, f"expected seeded fact among results, got: {result.chunks}"

    print(f"Recall found {len(result.chunks)} chunk(s), including the seeded fact")
    print("\nAll checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
