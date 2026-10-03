"""Run: python secondbrain/tools/tests/real_finder_check.py"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from secondbrain.config import settings  # noqa: E402
from secondbrain.integrations.supermemory_client import write_memory  # noqa: E402
from secondbrain.tools.finder import Finder  # noqa: E402


async def main() -> None:
    if not settings.supermemory_api_key:
        print("SUPERMEMORY_API_KEY not set in .env -- nothing to run")
        return

    notebook_id = f"finder-check-{int(time.time())}"
    content = "The quarterly report deadline has been moved to April 15th due to the audit delay."

    await write_memory(content=content, container_tag=f"notebook:{notebook_id}", metadata={"probe": True})
    print("seeded real content, waiting for Supermemory to index it...")
    await asyncio.sleep(8)

    result = await Finder().run({"notebook_id": notebook_id, "user_id": "n/a"}, "quarterly report deadline")

    assert result.ok, result.error
    assert result.chunks, "expected Finder to find the seeded content"
    found = any("April 15th" in (c.get("content") or c.get("memory") or "") for c in result.chunks)
    assert found, f"expected seeded content among results, got: {result.chunks}"

    print(f"Finder found {len(result.chunks)} chunk(s), including the seeded content")
    print("\nAll checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
