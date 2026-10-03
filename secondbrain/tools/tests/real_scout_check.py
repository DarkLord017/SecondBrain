"""Run: python secondbrain/tools/tests/real_scout_check.py"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from secondbrain.config import settings  # noqa: E402
from secondbrain.tools.scout import MAX_RESULTS, Scout  # noqa: E402


async def main() -> None:
    if not settings.tavily_api_key:
        print("TAVILY_API_KEY not set in .env -- nothing to run")
        return

    result = await Scout().run({"notebook_id": "n/a", "user_id": "n/a"}, "capital of France")

    assert result.ok, result.error
    assert result.chunks, "expected Scout to return real web results"
    assert len(result.chunks) <= MAX_RESULTS
    found = any("paris" in (c.get("content") or c.get("title") or "").lower() for c in result.chunks)
    assert found, f"expected a Paris-related result, got: {result.chunks}"

    print(f"Scout found {len(result.chunks)} real web result(s):")
    for c in result.chunks:
        print(" -", c.get("title"), "|", c.get("url"))

    print("\nAll checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
